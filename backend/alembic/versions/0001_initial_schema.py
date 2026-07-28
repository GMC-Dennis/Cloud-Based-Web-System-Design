"""Initial schema per TDD v1.2 section 4

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-28

Transcribed directly from the TDD's SQL (triggers, checks, view included)
so the deployed schema matches what was specified and reviewed, rather than
letting an ORM-generated migration drift from it.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UPGRADE_SQL = """
-- =====================================================================
-- USERS & SESSIONS
-- =====================================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('MERCHANT', 'CHAMA_MEMBER', 'UNDERWRITER')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT chk_deleted_after_created CHECK (deleted_at IS NULL OR deleted_at >= created_at)
);
CREATE INDEX idx_users_active ON users(id) WHERE deleted_at IS NULL;

CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    token_hash VARCHAR(128) NOT NULL,
    replaced_by UUID REFERENCES refresh_tokens(id),
    issued_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX idx_refresh_tokens_user ON refresh_tokens(user_id) WHERE revoked_at IS NULL;

CREATE TABLE otp_challenges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(20) NOT NULL,
    code_hash VARCHAR(128) NOT NULL,
    attempt_count INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    consumed_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX idx_otp_phone_recent ON otp_challenges(phone_number, created_at DESC);

-- =====================================================================
-- MERCHANT DUKA LEDGER (Immutable, Append-Only)
-- =====================================================================

CREATE TABLE duka_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    sequence_no BIGINT NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'KES',
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('SALE', 'EXPENSE', 'SUPPLIER_PAYMENT')),
    is_credit BOOLEAN DEFAULT FALSE,
    customer_phone VARCHAR(20),
    previous_hash VARCHAR(64) NOT NULL,
    record_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (merchant_id, sequence_no)
);

CREATE INDEX idx_ledger_merchant ON duka_transactions(merchant_id, created_at DESC);
CREATE INDEX idx_ledger_customer ON duka_transactions(customer_phone) WHERE customer_phone IS NOT NULL;

CREATE OR REPLACE FUNCTION prevent_ledger_mutation() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'duka_transactions is append-only: % is not permitted', TG_OP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_no_update_ledger
    BEFORE UPDATE OR DELETE ON duka_transactions
    FOR EACH ROW EXECUTE FUNCTION prevent_ledger_mutation();

CREATE OR REPLACE FUNCTION validate_ledger_chain() RETURNS TRIGGER AS $$
DECLARE
    expected_prev_hash VARCHAR(64);
BEGIN
    IF NEW.sequence_no = 1 THEN
        expected_prev_hash := repeat('0', 64);
    ELSE
        SELECT record_hash INTO expected_prev_hash
        FROM duka_transactions
        WHERE merchant_id = NEW.merchant_id AND sequence_no = NEW.sequence_no - 1;

        IF expected_prev_hash IS NULL THEN
            RAISE EXCEPTION 'duka_transactions chain gap: merchant % has no row at sequence_no %',
                NEW.merchant_id, NEW.sequence_no - 1;
        END IF;
    END IF;

    IF NEW.previous_hash IS DISTINCT FROM expected_prev_hash THEN
        RAISE EXCEPTION 'duka_transactions chain break: merchant % sequence_no % previous_hash mismatch',
            NEW.merchant_id, NEW.sequence_no;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validate_ledger_chain
    BEFORE INSERT ON duka_transactions
    FOR EACH ROW EXECUTE FUNCTION validate_ledger_chain();

-- =====================================================================
-- INVENTORY
-- =====================================================================

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL,
    unit_cost DECIMAL(12, 2) NOT NULL,
    unit_price DECIMAL(12, 2) NOT NULL,
    quantity_on_hand INT NOT NULL DEFAULT 0 CHECK (quantity_on_hand >= 0),
    reorder_threshold INT DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_products_merchant ON products(merchant_id);

CREATE TABLE inventory_movements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    duka_transaction_id UUID REFERENCES duka_transactions(id) ON DELETE RESTRICT,
    quantity_delta INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_inventory_movements_product ON inventory_movements(product_id, created_at DESC);

CREATE OR REPLACE FUNCTION apply_inventory_movement() RETURNS TRIGGER AS $$
BEGIN
    UPDATE products
    SET quantity_on_hand = quantity_on_hand + NEW.quantity_delta,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.product_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_apply_inventory_movement
    AFTER INSERT ON inventory_movements
    FOR EACH ROW EXECUTE FUNCTION apply_inventory_movement();

-- =====================================================================
-- CHAMA GROUP SAVINGS
-- =====================================================================

CREATE TABLE chama_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_name VARCHAR(100) NOT NULL,
    contribution_cycle VARCHAR(20) NOT NULL CHECK (contribution_cycle IN ('WEEKLY', 'MONTHLY')),
    cycle_amount DECIMAL(12, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chama_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chama_id UUID NOT NULL REFERENCES chama_groups(id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    member_role VARCHAR(20) NOT NULL DEFAULT 'MEMBER'
        CHECK (member_role IN ('CHAIRPERSON', 'TREASURER', 'SECRETARY', 'MEMBER')),
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (chama_id, user_id)
);

CREATE TABLE chama_contributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chama_id UUID NOT NULL REFERENCES chama_groups(id) ON DELETE RESTRICT,
    member_id UUID NOT NULL REFERENCES chama_members(id) ON DELETE RESTRICT,
    cycle_due_date DATE NOT NULL,
    amount_due DECIMAL(12, 2) NOT NULL,
    amount_paid DECIMAL(12, 2) NOT NULL DEFAULT 0,
    paid_at TIMESTAMP WITH TIME ZONE,
    is_on_time BOOLEAN,
    UNIQUE (member_id, cycle_due_date)
);
CREATE INDEX idx_chama_contrib_member ON chama_contributions(member_id, cycle_due_date DESC);

CREATE TABLE chama_payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chama_id UUID NOT NULL REFERENCES chama_groups(id) ON DELETE RESTRICT,
    recipient_member_id UUID NOT NULL REFERENCES chama_members(id) ON DELETE RESTRICT,
    payout_amount DECIMAL(12, 2) NOT NULL,
    scheduled_date DATE NOT NULL,
    paid_out_at TIMESTAMP WITH TIME ZONE
);

-- =====================================================================
-- CREDIT SCORING & LOANS
-- =====================================================================

CREATE TABLE credit_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    credit_score INT NOT NULL CHECK (credit_score BETWEEN 300 AND 850),
    recommended_limit DECIMAL(12, 2) NOT NULL,
    risk_tier VARCHAR(20) NOT NULL CHECK (risk_tier IN ('LOW', 'MEDIUM', 'HIGH')),
    model_version VARCHAR(30) NOT NULL,
    shap_explanation JSONB NOT NULL,
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_scoring_user ON credit_scores(user_id, evaluated_at DESC);

CREATE TABLE loans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    borrower_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    credit_score_id UUID REFERENCES credit_scores(id) ON DELETE RESTRICT,
    underwriting_method VARCHAR(20) NOT NULL DEFAULT 'ALGORITHMIC'
        CHECK (underwriting_method IN ('ALGORITHMIC', 'MANUAL', 'OVERRIDE')),
    override_reason TEXT,
    principal DECIMAL(12, 2) NOT NULL,
    interest_rate DECIMAL(5, 4) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'APPROVED', 'DISBURSED', 'REPAID', 'DEFAULTED', 'REJECTED')),
    disbursed_at TIMESTAMP WITH TIME ZONE,
    due_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_algorithmic_has_score
        CHECK (underwriting_method <> 'ALGORITHMIC' OR credit_score_id IS NOT NULL)
);

CREATE TABLE loan_repayments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    loan_id UUID NOT NULL REFERENCES loans(id) ON DELETE RESTRICT,
    amount DECIMAL(12, 2) NOT NULL,
    paid_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_loan_repayments_loan ON loan_repayments(loan_id, paid_at DESC);

-- =====================================================================
-- ANONYMIZED UNDERWRITER READ MODEL
-- =====================================================================

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
"""

DOWNGRADE_SQL = """
DROP VIEW IF EXISTS underwriter_applicant_view;
DROP TABLE IF EXISTS loan_repayments;
DROP TABLE IF EXISTS loans;
DROP TABLE IF EXISTS credit_scores;
DROP TABLE IF EXISTS chama_payouts;
DROP TABLE IF EXISTS chama_contributions;
DROP TABLE IF EXISTS chama_members;
DROP TABLE IF EXISTS chama_groups;
DROP TRIGGER IF EXISTS trg_apply_inventory_movement ON inventory_movements;
DROP FUNCTION IF EXISTS apply_inventory_movement();
DROP TABLE IF EXISTS inventory_movements;
DROP TABLE IF EXISTS products;
DROP TRIGGER IF EXISTS trg_validate_ledger_chain ON duka_transactions;
DROP FUNCTION IF EXISTS validate_ledger_chain();
DROP TRIGGER IF EXISTS trg_no_update_ledger ON duka_transactions;
DROP FUNCTION IF EXISTS prevent_ledger_mutation();
DROP TABLE IF EXISTS duka_transactions;
DROP TABLE IF EXISTS otp_challenges;
DROP TABLE IF EXISTS refresh_tokens;
DROP TABLE IF EXISTS users;
"""


def upgrade() -> None:
    op.execute(UPGRADE_SQL)


def downgrade() -> None:
    op.execute(DOWNGRADE_SQL)
