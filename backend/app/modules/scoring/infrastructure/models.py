import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class CreditScore(Base):
    __tablename__ = "credit_scores"
    __table_args__ = (CheckConstraint("credit_score BETWEEN 300 AND 850", name="chk_credit_score_range"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    credit_score: Mapped[int] = mapped_column(nullable=False)
    recommended_limit: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)
    shap_explanation: Mapped[dict] = mapped_column(JSONB, nullable=False)
    anomaly_flags: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint(
            "underwriting_method <> 'ALGORITHMIC' OR credit_score_id IS NOT NULL",
            name="chk_algorithmic_has_score",
        ),
        CheckConstraint(
            "underwriting_method IN ('ALGORITHMIC', 'MANUAL', 'OVERRIDE')", name="chk_underwriting_method"
        ),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'DISBURSED', 'REPAID', 'DEFAULTED', 'REJECTED')", name="chk_loan_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    borrower_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    credit_score_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_scores.id", ondelete="RESTRICT"), nullable=True
    )
    underwriting_method: Mapped[str] = mapped_column(String(20), nullable=False, default="ALGORITHMIC")
    override_reason: Mapped[str | None] = mapped_column(nullable=True)
    principal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    interest_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class LoanRepayment(Base):
    __tablename__ = "loan_repayments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    loan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("loans.id", ondelete="RESTRICT"), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
