"""Admin action audit log (ADMIN spec §4.1).

`users.created_by` only records who *created* an account -- nothing
independently records who changed a role, deactivated, or reactivated a
user later. This closes that gap for accountability on a platform that
hands out loan-approval authority.

Lives in `core/` rather than inside the `identity` module, mirroring the
precedent set by `idempotency.py`: this is cross-cutting infrastructure
(conceivably other modules could want to write to it later) rather than
identity-specific domain logic, so it shouldn't be identity's job to own
it. To keep that decoupling real, this module knows nothing about
`identity`'s `User` model -- it only ever sees user IDs. Display-level
enrichment (resolving actor/target names) is the presentation layer's
job, done via the identity user repository.

Append-only, same precedent (and same reason) as `duka_transactions`
(TDD §4): an audit log that can be edited after the fact isn't one.
Enforced with a DB trigger (migration 0004) rather than just discipline
in Python, since the whole point is to survive a buggy or compromised
caller.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func, select
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

ADMIN_AUDIT_ACTIONS = ("CREATE_USER", "UPDATE_USER", "DEACTIVATE_USER", "REACTIVATE_USER")


class AdminAuditLogRecord(Base):
    __tablename__ = "admin_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


@dataclass
class AuditLogEntry:
    id: str
    actor_user_id: str
    target_user_id: str | None
    action: str
    detail: dict[str, Any] | None
    created_at: datetime


def _to_entry(row: AdminAuditLogRecord) -> AuditLogEntry:
    return AuditLogEntry(
        id=str(row.id),
        actor_user_id=str(row.actor_user_id),
        target_user_id=str(row.target_user_id) if row.target_user_id else None,
        action=row.action,
        detail=row.detail,
        created_at=row.created_at,
    )


class AuditLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(
        self, *, actor_user_id: str, target_user_id: str | None, action: str, detail: dict[str, Any] | None = None
    ) -> None:
        self.session.add(
            AdminAuditLogRecord(
                actor_user_id=uuid.UUID(actor_user_id),
                target_user_id=uuid.UUID(target_user_id) if target_user_id else None,
                action=action,
                detail=detail,
            )
        )
        await self.session.flush()

    async def list_all(
        self,
        *,
        limit: int,
        offset: int,
        target_user_id: str | None = None,
        actor_user_id: str | None = None,
        action: str | None = None,
    ) -> tuple[list[AuditLogEntry], int]:
        conditions = []
        if target_user_id is not None:
            conditions.append(AdminAuditLogRecord.target_user_id == uuid.UUID(target_user_id))
        if actor_user_id is not None:
            conditions.append(AdminAuditLogRecord.actor_user_id == uuid.UUID(actor_user_id))
        if action is not None:
            conditions.append(AdminAuditLogRecord.action == action)

        total = (await self.session.execute(select(func.count()).select_from(AdminAuditLogRecord).where(*conditions))).scalar_one()
        rows = (
            await self.session.execute(
                select(AdminAuditLogRecord)
                .where(*conditions)
                .order_by(AdminAuditLogRecord.created_at.desc(), AdminAuditLogRecord.id)
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
        return [_to_entry(r) for r in rows], total
