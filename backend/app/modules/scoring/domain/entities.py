from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass
class CreditScore:
    id: str
    user_id: str
    credit_score: int
    recommended_limit: Decimal
    risk_tier: str
    model_version: str
    shap_explanation: dict
    evaluated_at: datetime


@dataclass
class Loan:
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


@dataclass
class LoanRepayment:
    id: str
    loan_id: str
    amount: Decimal
    paid_at: datetime


@dataclass
class ApplicantView:
    credit_score_id: str
    loan_id: str | None
    credit_score: int
    risk_tier: str
    recommended_limit: Decimal
    shap_explanation: dict
    applicant_name: str | None
    applicant_phone: str | None
    status: str | None
