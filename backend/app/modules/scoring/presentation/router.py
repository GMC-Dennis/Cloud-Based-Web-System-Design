from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentUser, get_current_user, require_role
from app.core.pagination import Page, PageParams
from app.modules.chama.infrastructure.repository import SqlChamaContributionRepository, SqlChamaMemberRepository
from app.modules.ledger.infrastructure.repository import SqlLedgerRepository, SqlProductRepository
from app.modules.scoring.application.use_cases import (
    ComputeMerchantFeatures,
    CreateLoan,
    EvaluateMerchant,
    ListApplicants,
    RecordRepayment,
)
from app.modules.scoring.infrastructure.repository import SqlCreditScoreRepository, SqlLoanRepository
from app.modules.scoring.infrastructure.scoring_engine import AlternativeCreditScorer
from app.modules.scoring.presentation.schemas import (
    ApplicantOut,
    CreateLoanIn,
    CreditScoreOut,
    LoanOut,
    RecordRepaymentIn,
    RepaymentOut,
)

router = APIRouter(tags=["scoring"])


def _get_engine(request: Request) -> AlternativeCreditScorer:
    engine = request.app.state.scoring_engine
    if engine is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Scoring model not loaded; run train_model.py")
    return engine


@router.post("/scoring/evaluate/{user_id}", response_model=CreditScoreOut)
async def evaluate_merchant(
    user_id: str, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user), engine: AlternativeCreditScorer = Depends(_get_engine)
) -> CreditScoreOut:
    if user.id != user_id and user.role != "UNDERWRITER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot evaluate another merchant")

    compute_features = ComputeMerchantFeatures(
        SqlLedgerRepository(db), SqlProductRepository(db), SqlChamaMemberRepository(db), SqlChamaContributionRepository(db)
    )
    score = await EvaluateMerchant(compute_features, engine, SqlCreditScoreRepository(db)).execute(user_id)
    await db.commit()
    return CreditScoreOut(**score.__dict__)


@router.get("/scoring/scores/{user_id}/latest", response_model=CreditScoreOut)
async def latest_score(user_id: str, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> CreditScoreOut:
    if user.id != user_id and user.role != "UNDERWRITER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot view another merchant's score")
    score = await SqlCreditScoreRepository(db).latest_for_user(user_id)
    if score is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No score on file for this user")
    return CreditScoreOut(**score.__dict__)


@router.post("/loans", response_model=LoanOut, dependencies=[Depends(require_role("UNDERWRITER"))])
async def create_loan(body: CreateLoanIn, db: AsyncSession = Depends(get_db)) -> LoanOut:
    score_repo = SqlCreditScoreRepository(db)
    borrower_id = body.borrower_id
    if borrower_id is None and body.credit_score_id is not None:
        # Resolves the borrower from the score the underwriter is acting on --
        # the anonymized underwriter_applicant_view they're working from never
        # hands them a raw user_id directly (see CreateLoanIn's docstring).
        score = await score_repo.get(body.credit_score_id)
        if score is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "credit_score_id does not exist")
        borrower_id = score.user_id
    if borrower_id is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "borrower_id is required when no credit_score_id is given")

    try:
        loan = await CreateLoan(SqlLoanRepository(db), score_repo).execute(
            borrower_id=borrower_id,
            underwriting_method=body.underwriting_method,
            principal=body.principal,
            interest_rate=body.interest_rate,
            credit_score_id=body.credit_score_id,
            override_reason=body.override_reason,
            due_date=body.due_date,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    await db.commit()
    return LoanOut(**loan.__dict__)


@router.get("/loans/mine", response_model=Page[LoanOut])
async def my_loans(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user), page: PageParams = Depends()
) -> Page[LoanOut]:
    loans, total = await SqlLoanRepository(db).list_for_borrower(user.id, page.limit, page.offset)
    return Page(items=[LoanOut(**l.__dict__) for l in loans], total=total, limit=page.limit, offset=page.offset)


@router.post("/loans/{loan_id}/repayments", response_model=RepaymentOut)
async def record_repayment(loan_id: str, body: RecordRepaymentIn, db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(get_current_user)) -> RepaymentOut:
    repayment = await RecordRepayment(SqlLoanRepository(db)).execute(loan_id, body.amount)
    await db.commit()
    return RepaymentOut(**repayment.__dict__)


@router.get("/underwriter/applicants", response_model=Page[ApplicantOut], dependencies=[Depends(require_role("UNDERWRITER"))])
async def list_applicants(db: AsyncSession = Depends(get_db), page: PageParams = Depends()) -> Page[ApplicantOut]:
    applicants, total = await ListApplicants(SqlLoanRepository(db)).execute(page.limit, page.offset)
    return Page(items=[ApplicantOut(**a.__dict__) for a in applicants], total=total, limit=page.limit, offset=page.offset)
