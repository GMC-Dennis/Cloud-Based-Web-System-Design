from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class CreditScoreOut(BaseModel):
    id: str
    user_id: str
    credit_score: int
    recommended_limit: Decimal
    risk_tier: str
    model_version: str
    shap_explanation: dict[str, float]
    evaluated_at: datetime


class CreateLoanIn(BaseModel):
    # borrower_id is optional for ALGORITHMIC loans: the underwriter portal
    # works off the anonymized underwriter_applicant_view (TDD §4/§8.1),
    # which never exposes a raw user_id -- only credit_score_id. The router
    # resolves borrower_id server-side from credit_score_id in that case.
    # MANUAL/OVERRIDE loans (no algorithmic score backing them) still need
    # borrower_id supplied directly, since there's no score row to resolve it from.
    borrower_id: str | None = None
    underwriting_method: str = "ALGORITHMIC"
    credit_score_id: str | None = None
    override_reason: str | None = None
    principal: Decimal
    interest_rate: Decimal
    due_date: date | None = None


class LoanOut(BaseModel):
    id: str
    borrower_id: str
    credit_score_id: str | None
    underwriting_method: str
    override_reason: str | None
    principal: Decimal
    interest_rate: Decimal
    status: str
    disbursed_at: datetime | None
    due_date: date | None
    created_at: datetime


class RecordRepaymentIn(BaseModel):
    amount: Decimal


class RepaymentOut(BaseModel):
    id: str
    loan_id: str
    amount: Decimal
    paid_at: datetime


class ApplicantOut(BaseModel):
    credit_score_id: str
    loan_id: str | None
    credit_score: int
    risk_tier: str
    recommended_limit: Decimal
    shap_explanation: dict[str, float]
    applicant_name: str | None
    applicant_phone: str | None
    status: str | None
