"""Idempotency-key support for financial write endpoints (TDD v1.3).

A client retrying a timed-out sale/expense/supplier-payment request over a
flaky mobile connection must not create a second real ledger entry. Callers
pass an `Idempotency-Key` header; the first successful call's response is
stored keyed on (user, key, endpoint) and replayed verbatim on any retry
with the same key, instead of re-running the write.

Handles the common case -- a client retry sent *after* the first request's
transaction has already committed. Two truly simultaneous requests with the
same key can both execute their write and both attempt to record the
response; only one insert can win the UNIQUE(user_id, idempotency_key,
endpoint) constraint, so the loser's entire transaction (including its
ledger write) rolls back and that caller sees a 500. Retrying converges to
the single correct result, so this is a rare, self-healing edge case rather
than a duplicate-money bug -- not worth the complexity of finer-grained
locking unless it's observed in practice.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class IdempotencyKeyRecord(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key", "endpoint"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


async def _get_cached(db: AsyncSession, *, user_id: str, idempotency_key: str, endpoint: str) -> dict[str, Any] | None:
    row = (
        await db.execute(
            select(IdempotencyKeyRecord).where(
                IdempotencyKeyRecord.user_id == uuid.UUID(user_id),
                IdempotencyKeyRecord.idempotency_key == idempotency_key,
                IdempotencyKeyRecord.endpoint == endpoint,
            )
        )
    ).scalar_one_or_none()
    return row.response_body if row is not None else None


async def idempotent(
    db: AsyncSession,
    *,
    user_id: str,
    idempotency_key: str | None,
    endpoint: str,
    execute: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """Runs `execute()` at most once per (user, idempotency_key, endpoint).

    `execute` must return a JSON-serializable dict (e.g. a Pydantic model's
    `.model_dump(mode="json")`). No-op passthrough when no key is supplied --
    idempotency is opt-in from the client, not forced.
    """
    if idempotency_key is None:
        return await execute()

    cached = await _get_cached(db, user_id=user_id, idempotency_key=idempotency_key, endpoint=endpoint)
    if cached is not None:
        return cached

    body = await execute()
    db.add(
        IdempotencyKeyRecord(
            user_id=uuid.UUID(user_id), idempotency_key=idempotency_key, endpoint=endpoint, response_status=200, response_body=body
        )
    )
    await db.flush()
    return body
