from datetime import date, datetime, timezone
from decimal import Decimal

from redis.asyncio import Redis

from app.core.cache import invalidate_score_cache
from app.modules.chama.domain.entities import ChamaContribution, ChamaGroup, ChamaMember, ChamaPayout
from app.modules.chama.domain.repository import (
    ChamaContributionRepository,
    ChamaGroupRepository,
    ChamaMemberRepository,
    ChamaPayoutRepository,
)


class CreateChama:
    def __init__(self, group_repo: ChamaGroupRepository, member_repo: ChamaMemberRepository):
        self.group_repo = group_repo
        self.member_repo = member_repo

    async def execute(self, *, group_name: str, contribution_cycle: str, cycle_amount: Decimal, creator_user_id: str) -> ChamaGroup:
        group = await self.group_repo.create(group_name=group_name, contribution_cycle=contribution_cycle, cycle_amount=cycle_amount)
        await self.member_repo.add(chama_id=group.id, user_id=creator_user_id, member_role="CHAIRPERSON")
        return group


class AddMember:
    def __init__(self, member_repo: ChamaMemberRepository):
        self.member_repo = member_repo

    async def execute(self, *, chama_id: str, user_id: str, member_role: str = "MEMBER") -> ChamaMember:
        return await self.member_repo.add(chama_id=chama_id, user_id=user_id, member_role=member_role)


class RecordContribution:
    def __init__(self, contribution_repo: ChamaContributionRepository, redis: Redis | None = None):
        self.contribution_repo = contribution_repo
        self.redis = redis

    async def execute(
        self, *, chama_id: str, member_id: str, cycle_due_date: date, amount_due: Decimal, amount_paid: Decimal, paid_at: datetime | None, user_id: str
    ) -> ChamaContribution:
        paid_at = paid_at or datetime.now(timezone.utc)
        is_on_time = paid_at.date() <= cycle_due_date
        contribution = await self.contribution_repo.record(
            chama_id=chama_id, member_id=member_id, cycle_due_date=cycle_due_date, amount_due=amount_due, amount_paid=amount_paid, paid_at=paid_at, is_on_time=is_on_time
        )
        if self.redis is not None:
            await invalidate_score_cache(self.redis, user_id)
        return contribution


class SchedulePayout:
    def __init__(self, payout_repo: ChamaPayoutRepository):
        self.payout_repo = payout_repo

    async def execute(self, *, chama_id: str, recipient_member_id: str, payout_amount: Decimal, scheduled_date: date) -> ChamaPayout:
        return await self.payout_repo.schedule(chama_id=chama_id, recipient_member_id=recipient_member_id, payout_amount=payout_amount, scheduled_date=scheduled_date)


class GetPunctuality:
    def __init__(self, contribution_repo: ChamaContributionRepository):
        self.contribution_repo = contribution_repo

    async def execute(self, member_id: str) -> float:
        return await self.contribution_repo.punctuality(member_id)


class ListMyChamas:
    def __init__(self, group_repo: ChamaGroupRepository):
        self.group_repo = group_repo

    async def execute(self, user_id: str, limit: int, offset: int) -> tuple[list[ChamaGroup], int]:
        return await self.group_repo.list_for_user(user_id, limit, offset)


class ListMembers:
    def __init__(self, member_repo: ChamaMemberRepository):
        self.member_repo = member_repo

    async def execute(self, chama_id: str, limit: int, offset: int) -> tuple[list[ChamaMember], int]:
        return await self.member_repo.list_for_chama(chama_id, limit, offset)
