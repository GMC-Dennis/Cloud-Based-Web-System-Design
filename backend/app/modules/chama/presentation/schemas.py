from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class CreateChamaIn(BaseModel):
    group_name: str
    contribution_cycle: str
    cycle_amount: Decimal


class ChamaGroupOut(BaseModel):
    id: str
    group_name: str
    contribution_cycle: str
    cycle_amount: Decimal
    created_at: datetime


class AddMemberIn(BaseModel):
    user_id: str
    member_role: str = "MEMBER"


class ChamaMemberOut(BaseModel):
    id: str
    chama_id: str
    user_id: str
    member_role: str
    joined_at: datetime


class RecordContributionIn(BaseModel):
    member_id: str
    cycle_due_date: date
    amount_due: Decimal
    amount_paid: Decimal
    paid_at: datetime | None = None


class ContributionOut(BaseModel):
    id: str
    chama_id: str
    member_id: str
    cycle_due_date: date
    amount_due: Decimal
    amount_paid: Decimal
    paid_at: datetime | None
    is_on_time: bool | None


class SchedulePayoutIn(BaseModel):
    recipient_member_id: str
    payout_amount: Decimal
    scheduled_date: date


class PayoutOut(BaseModel):
    id: str
    chama_id: str
    recipient_member_id: str
    payout_amount: Decimal
    scheduled_date: date
    paid_out_at: datetime | None


class PunctualityOut(BaseModel):
    member_id: str
    punctuality_pct: float
