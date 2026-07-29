from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.modules.scoring.domain.entities import ApplicantView, CreditScore, Loan, LoanRepayment


class CreditScoreRepository(Protocol):
    async def save(
        self,
        *,
        user_id: str,
        credit_score: int,
        recommended_limit: Decimal,
        risk_tier: str,
        model_version: str,
        shap_explanation: dict,
        anomaly_flags: list[str],
    ) -> CreditScore: ...
    async def get(self, credit_score_id: str) -> CreditScore | None: ...
    async def latest_for_user(self, user_id: str) -> CreditScore | None: ...


class LoanRepository(Protocol):
    async def create(
        self,
        *,
        borrower_id: str,
        credit_score_id: str | None,
        underwriting_method: str,
        override_reason: str | None,
        principal: Decimal,
        interest_rate: Decimal,
        due_date: date | None,
    ) -> Loan: ...
    async def get(self, loan_id: str) -> Loan | None: ...
    async def list_for_borrower(self, borrower_id: str, limit: int, offset: int) -> tuple[list[Loan], int]: ...
    async def record_repayment(self, loan_id: str, amount: Decimal) -> LoanRepayment: ...
    async def list_applicants(self, limit: int, offset: int) -> tuple[list[ApplicantView], int]: ...
    async def list_repayments_for_loan(self, loan_id: str, limit: int, offset: int) -> tuple[list[LoanRepayment], int]: ...
