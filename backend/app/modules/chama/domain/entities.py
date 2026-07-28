from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass
class ChamaGroup:
    id: str
    group_name: str
    contribution_cycle: str
    cycle_amount: Decimal
    created_at: datetime


@dataclass
class ChamaMember:
    id: str
    chama_id: str
    user_id: str
    member_role: str
    joined_at: datetime


@dataclass
class ChamaContribution:
    id: str
    chama_id: str
    member_id: str
    cycle_due_date: date
    amount_due: Decimal
    amount_paid: Decimal
    paid_at: datetime | None
    is_on_time: bool | None


@dataclass
class ChamaPayout:
    id: str
    chama_id: str
    recipient_member_id: str
    payout_amount: Decimal
    scheduled_date: date
    paid_out_at: datetime | None
