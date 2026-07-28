"""Add admin_audit_log (ADMIN spec §4.1)

Revision ID: 0004_admin_audit_log
Revises: 0003_admin_role
Create Date: 2026-07-28

Independent record of who did what to whom for the four admin
user-management actions -- `users.created_by` only tells you who created
an account, nothing records a later role change, deactivation, or
reactivation. Append-only, same precedent (and same reason) as
`duka_transactions` in 0001_initial_schema: a trigger enforces it at the
DB level rather than trusting every future caller to only ever INSERT.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004_admin_audit_log"
down_revision: Union[str, None] = "0003_admin_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
CREATE TABLE admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    target_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(30) NOT NULL CHECK (action IN ('CREATE_USER', 'UPDATE_USER', 'DEACTIVATE_USER', 'REACTIVATE_USER')),
    detail JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_admin_audit_log_actor ON admin_audit_log(actor_user_id, created_at DESC);
CREATE INDEX idx_admin_audit_log_target ON admin_audit_log(target_user_id, created_at DESC);

CREATE OR REPLACE FUNCTION prevent_audit_log_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'admin_audit_log is append-only: % is not permitted', TG_OP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_no_update_admin_audit_log
    BEFORE UPDATE OR DELETE ON admin_audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();
"""

DOWNGRADE_SQL = """
DROP TRIGGER IF EXISTS trg_no_update_admin_audit_log ON admin_audit_log;
DROP FUNCTION IF EXISTS prevent_audit_log_mutation();
DROP TABLE IF EXISTS admin_audit_log;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
