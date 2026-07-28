"""Add idempotency_keys table (TDD v1.3)

Revision ID: 0002_idempotency_keys
Revises: 0001_initial_schema
Create Date: 2026-07-28

Backs Idempotency-Key support on the ledger's write endpoints (sale/expense/
supplier-payment) -- a client retry after a timed-out request must not
create a second real transaction. See app/core/idempotency.py.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_idempotency_keys"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("endpoint", sa.String(100), nullable=False),
        sa.Column("response_status", sa.Integer, nullable=False),
        sa.Column("response_body", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("user_id", "idempotency_key", "endpoint", name="uq_idempotency_key_per_user_endpoint"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
