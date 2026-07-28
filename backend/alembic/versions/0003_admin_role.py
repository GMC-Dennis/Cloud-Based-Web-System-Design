"""Add ADMIN role and users.created_by (TDD v1.4)

Revision ID: 0003_admin_role
Revises: 0002_idempotency_keys
Create Date: 2026-07-28

Backs admin-provisioned underwriter onboarding and user management. Also
restricts self-registration (the public OTP signup flow) to MERCHANT/
CHAMA_MEMBER only -- ADMIN and UNDERWRITER accounts must be created by an
existing admin, closing the gap where anyone could self-assign the
UNDERWRITER role at signup.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_admin_role"
down_revision: Union[str, None] = "0002_idempotency_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Named "users_role_check" by Postgres's default convention for an
    # unnamed inline CHECK -- migration 0001 declared it that way (raw SQL,
    # no explicit constraint name), so that's the name that actually exists.
    op.drop_constraint("users_role_check", "users", type_="check")
    op.create_check_constraint(
        "chk_users_role", "users", "role IN ('MERCHANT', 'CHAMA_MEMBER', 'UNDERWRITER', 'ADMIN')"
    )
    op.add_column("users", sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "created_by")
    op.drop_constraint("chk_users_role", "users", type_="check")
    op.create_check_constraint(
        "users_role_check", "users", "role IN ('MERCHANT', 'CHAMA_MEMBER', 'UNDERWRITER')"
    )
