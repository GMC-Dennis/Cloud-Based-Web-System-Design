import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scoring.domain.entities import ApplicantView, CreditScore, Loan, LoanRepayment
from app.modules.scoring.infrastructure.models import CreditScore as CreditScoreModel
from app.modules.scoring.infrastructure.models import Loan as LoanModel
from app.modules.scoring.infrastructure.models import LoanRepayment as RepaymentModel


def _to_score(row: CreditScoreModel) -> CreditScore:
    return CreditScore(
        id=str(row.id), user_id=str(row.user_id), credit_score=row.credit_score, recommended_limit=row.recommended_limit,
        risk_tier=row.risk_tier, model_version=row.model_version, shap_explanation=row.shap_explanation, evaluated_at=row.evaluated_at,
    )


def _to_loan(row: LoanModel) -> Loan:
    return Loan(
        id=str(row.id), borrower_id=str(row.borrower_id), credit_score_id=str(row.credit_score_id) if row.credit_score_id else None,
        underwriting_method=row.underwriting_method, override_reason=row.override_reason, principal=row.principal,
        interest_rate=row.interest_rate, status=row.status, disbursed_at=row.disbursed_at, due_date=row.due_date, created_at=row.created_at,
    )


class SqlCreditScoreRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(
        self, *, user_id: str, credit_score: int, recommended_limit: Decimal, risk_tier: str, model_version: str, shap_explanation: dict
    ) -> CreditScore:
        row = CreditScoreModel(
            user_id=uuid.UUID(user_id), credit_score=credit_score, recommended_limit=recommended_limit,
            risk_tier=risk_tier, model_version=model_version, shap_explanation=shap_explanation,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _to_score(row)

    async def get(self, credit_score_id: str) -> CreditScore | None:
        row = await self.session.get(CreditScoreModel, uuid.UUID(credit_score_id))
        return _to_score(row) if row else None

    async def latest_for_user(self, user_id: str) -> CreditScore | None:
        row = (
            await self.session.execute(
                select(CreditScoreModel).where(CreditScoreModel.user_id == uuid.UUID(user_id)).order_by(CreditScoreModel.evaluated_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        return _to_score(row) if row else None


class SqlLoanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

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
    ) -> Loan:
        row = LoanModel(
            borrower_id=uuid.UUID(borrower_id),
            credit_score_id=uuid.UUID(credit_score_id) if credit_score_id else None,
            underwriting_method=underwriting_method,
            override_reason=override_reason,
            principal=principal,
            interest_rate=interest_rate,
            due_date=due_date,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _to_loan(row)

    async def get(self, loan_id: str) -> Loan | None:
        row = await self.session.get(LoanModel, uuid.UUID(loan_id))
        return _to_loan(row) if row else None

    async def list_for_borrower(self, borrower_id: str, limit: int, offset: int) -> tuple[list[Loan], int]:
        total = (
            await self.session.execute(select(func.count()).select_from(LoanModel).where(LoanModel.borrower_id == uuid.UUID(borrower_id)))
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(LoanModel)
                .where(LoanModel.borrower_id == uuid.UUID(borrower_id))
                .order_by(LoanModel.created_at.desc(), LoanModel.id)
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
        return [_to_loan(r) for r in rows], total

    async def record_repayment(self, loan_id: str, amount: Decimal) -> LoanRepayment:
        row = RepaymentModel(loan_id=uuid.UUID(loan_id), amount=amount)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return LoanRepayment(id=str(row.id), loan_id=str(row.loan_id), amount=row.amount, paid_at=row.paid_at)

    async def list_applicants(self, limit: int, offset: int) -> tuple[list[ApplicantView], int]:
        # Reads the anonymized underwriter_applicant_view (TDD §4) -- never
        # the base tables -- so applicant identity stays masked pre-approval.
        total = (await self.session.execute(text("SELECT COUNT(*) FROM underwriter_applicant_view"))).scalar_one()
        rows = await self.session.execute(
            text("SELECT * FROM underwriter_applicant_view ORDER BY credit_score_id LIMIT :limit OFFSET :offset"),
            {"limit": limit, "offset": offset},
        )
        applicants = [
            ApplicantView(
                credit_score_id=str(r.credit_score_id),
                loan_id=str(r.loan_id) if r.loan_id else None,
                credit_score=r.credit_score,
                risk_tier=r.risk_tier,
                recommended_limit=r.recommended_limit,
                shap_explanation=r.shap_explanation,
                applicant_name=r.applicant_name,
                applicant_phone=r.applicant_phone,
                status=r.status,
            )
            for r in rows
        ]
        return applicants, total
