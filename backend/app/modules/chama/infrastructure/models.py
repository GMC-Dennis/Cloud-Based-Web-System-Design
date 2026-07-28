import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.db import Base


class ChamaGroup(Base):
    __tablename__ = "chama_groups"
    __table_args__ = (CheckConstraint("contribution_cycle IN ('WEEKLY', 'MONTHLY')", name="chk_contribution_cycle"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    group_name: Mapped[str] = mapped_column(String(100), nullable=False)
    contribution_cycle: Mapped[str] = mapped_column(String(20), nullable=False)
    cycle_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class ChamaMember(Base):
    __tablename__ = "chama_members"
    __table_args__ = (
        UniqueConstraint("chama_id", "user_id"),
        CheckConstraint(
            "member_role IN ('CHAIRPERSON', 'TREASURER', 'SECRETARY', 'MEMBER')", name="chk_member_role"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    chama_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chama_groups.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    member_role: Mapped[str] = mapped_column(String(20), nullable=False, default="MEMBER")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class ChamaContribution(Base):
    __tablename__ = "chama_contributions"
    __table_args__ = (UniqueConstraint("member_id", "cycle_due_date"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    chama_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chama_groups.id", ondelete="RESTRICT"), nullable=False)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chama_members.id", ondelete="RESTRICT"), nullable=False)
    cycle_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_due: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    amount_paid: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_on_time: Mapped[bool | None] = mapped_column(nullable=True)


class ChamaPayout(Base):
    __tablename__ = "chama_payouts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    chama_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chama_groups.id", ondelete="RESTRICT"), nullable=False)
    recipient_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chama_members.id", ondelete="RESTRICT"), nullable=False
    )
    payout_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
