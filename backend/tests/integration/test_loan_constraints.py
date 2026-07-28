from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.scoring.application.use_cases import CreateLoan
from app.modules.scoring.infrastructure.repository import SqlCreditScoreRepository, SqlLoanRepository


async def test_algorithmic_loan_without_credit_score_id_rejected_at_application_layer(db_session, test_user):
    with pytest.raises(ValueError):
        await CreateLoan(SqlLoanRepository(db_session), SqlCreditScoreRepository(db_session)).execute(
            borrower_id=test_user.id, underwriting_method="ALGORITHMIC", principal=Decimal("5000"), interest_rate=Decimal("0.05")
        )


async def test_manual_loan_without_override_reason_rejected_at_application_layer(db_session, test_user):
    with pytest.raises(ValueError):
        await CreateLoan(SqlLoanRepository(db_session), SqlCreditScoreRepository(db_session)).execute(
            borrower_id=test_user.id, underwriting_method="MANUAL", principal=Decimal("5000"), interest_rate=Decimal("0.05")
        )


async def test_algorithmic_loan_with_valid_score_succeeds(db_session, test_user):
    score = await SqlCreditScoreRepository(db_session).save(
        user_id=test_user.id, credit_score=700, recommended_limit=Decimal("10000"), risk_tier="MEDIUM", model_version="rf_v3_2026_06", shap_explanation={}
    )
    await db_session.flush()

    loan = await CreateLoan(SqlLoanRepository(db_session), SqlCreditScoreRepository(db_session)).execute(
        borrower_id=test_user.id, underwriting_method="ALGORITHMIC", credit_score_id=score.id, principal=Decimal("5000"), interest_rate=Decimal("0.05"), due_date=date(2026, 12, 1)
    )
    assert loan.id is not None
    assert loan.status == "PENDING"


async def test_db_check_constraint_is_the_backstop_even_bypassing_the_use_case(db_session, test_user):
    # Simulates a bug in application code that skips CreateLoan's own check --
    # chk_algorithmic_has_score at the DB layer must still catch it.
    from app.modules.scoring.infrastructure.models import Loan as LoanModel
    import uuid

    row = LoanModel(
        borrower_id=uuid.UUID(test_user.id), credit_score_id=None, underwriting_method="ALGORITHMIC",
        principal=Decimal("5000"), interest_rate=Decimal("0.05"),
    )
    db_session.add(row)
    with pytest.raises(IntegrityError):
        await db_session.flush()
