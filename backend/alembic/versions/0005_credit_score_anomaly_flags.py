"""Add credit_scores.anomaly_flags (platform-cross-cutting spec §3.4d)

Revision ID: 0005_credit_score_anomaly_flags
Revises: 0004_admin_audit_log
Create Date: 2026-07-28

Cheap heuristic triage flags (e.g. "more than 80% of 30-day revenue
occurred in the last 3 days") computed alongside a score and surfaced to
underwriters as a warning badge. Explicitly a triage aid, not a fraud
model. Kept as a sibling column rather than folded into shap_explanation,
which stays a pure feature-name -> SHAP-value float mapping; mixing flag
strings into that dict would break its typing for every existing reader.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005_credit_score_anomaly_flags"
down_revision: Union[str, None] = "0004_admin_audit_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
ALTER TABLE credit_scores ADD COLUMN anomaly_flags JSONB NOT NULL DEFAULT '[]'::jsonb;

DROP VIEW underwriter_applicant_view;

CREATE VIEW underwriter_applicant_view AS
SELECT
    cs.id AS credit_score_id,
    l.id AS loan_id,
    cs.credit_score,
    cs.risk_tier,
    cs.recommended_limit,
    cs.shap_explanation,
    cs.anomaly_flags,
    CASE WHEN l.status IN ('APPROVED', 'DISBURSED', 'REPAID')
         THEN u.full_name ELSE NULL END AS applicant_name,
    CASE WHEN l.status IN ('APPROVED', 'DISBURSED', 'REPAID')
         THEN u.phone_number ELSE NULL END AS applicant_phone,
    l.status
FROM credit_scores cs
JOIN users u ON u.id = cs.user_id
LEFT JOIN loans l ON l.credit_score_id = cs.id;
"""

DOWNGRADE_SQL = """
DROP VIEW underwriter_applicant_view;

CREATE VIEW underwriter_applicant_view AS
SELECT
    cs.id AS credit_score_id,
    l.id AS loan_id,
    cs.credit_score,
    cs.risk_tier,
    cs.recommended_limit,
    cs.shap_explanation,
    CASE WHEN l.status IN ('APPROVED', 'DISBURSED', 'REPAID')
         THEN u.full_name ELSE NULL END AS applicant_name,
    CASE WHEN l.status IN ('APPROVED', 'DISBURSED', 'REPAID')
         THEN u.phone_number ELSE NULL END AS applicant_phone,
    l.status
FROM credit_scores cs
JOIN users u ON u.id = cs.user_id
LEFT JOIN loans l ON l.credit_score_id = cs.id;

ALTER TABLE credit_scores DROP COLUMN anomaly_flags;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
