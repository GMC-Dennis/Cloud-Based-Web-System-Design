from datetime import date, datetime, timezone
from decimal import Decimal

from redis.asyncio import Redis

from app.core.cache import invalidate_score_cache
from app.modules.chama.application.exceptions import (
    CannotRecordOwnContribution,
    MemberNotFound,
    NotAMemberOfThisChama,
    NotAuthorizedToRecordContribution,
    NotAuthorizedToSchedulePayout,
)
from app.modules.chama.domain.entities import ChamaContribution, ChamaGroup, ChamaMember, ChamaPayout
from app.modules.chama.domain.repository import (
    ChamaContributionRepository,
    ChamaGroupRepository,
    ChamaMemberRepository,
    ChamaPayoutRepository,
)

OFFICER_ROLES = ("CHAIRPERSON", "TREASURER", "SECRETARY")


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
    def __init__(self, contribution_repo: ChamaContributionRepository, member_repo: ChamaMemberRepository, redis: Redis | None = None):
        self.contribution_repo = contribution_repo
        self.member_repo = member_repo
        self.redis = redis

    async def execute(
        self,
        *,
        chama_id: str,
        member_id: str,
        cycle_due_date: date,
        amount_due: Decimal,
        amount_paid: Decimal,
        paid_at: datetime | None,
        target_user_id: str,
        recorded_by_user_id: str,
    ) -> ChamaContribution:
        # Duty separation: a member can't attest to their own punctuality,
        # and only an officer of *this* chama can attest to anyone's.
        if recorded_by_user_id == target_user_id:
            raise CannotRecordOwnContribution("A member cannot record their own contribution")

        acting_membership = await self.member_repo.get_for_user(chama_id, recorded_by_user_id)
        if acting_membership is None or acting_membership.member_role not in OFFICER_ROLES:
            raise NotAuthorizedToRecordContribution("Only a chairperson, treasurer, or secretary of this chama can record a contribution")

        paid_at = paid_at or datetime.now(timezone.utc)
        is_on_time = paid_at.date() <= cycle_due_date
        contribution = await self.contribution_repo.record(
            chama_id=chama_id, member_id=member_id, cycle_due_date=cycle_due_date, amount_due=amount_due, amount_paid=amount_paid, paid_at=paid_at, is_on_time=is_on_time
        )
        if self.redis is not None:
            await invalidate_score_cache(self.redis, target_user_id)
        return contribution


class SchedulePayout:
    def __init__(self, payout_repo: ChamaPayoutRepository, member_repo: ChamaMemberRepository):
        self.payout_repo = payout_repo
        self.member_repo = member_repo

    async def execute(
        self, *, chama_id: str, recipient_member_id: str, payout_amount: Decimal, scheduled_date: date, scheduled_by_user_id: str
    ) -> ChamaPayout:
        # Same duty-separation precedent as RecordContribution: scheduling a
        # payout is a sensitive, officer-only action, not something any
        # authenticated user should be able to do for any chama.
        acting_membership = await self.member_repo.get_for_user(chama_id, scheduled_by_user_id)
        if acting_membership is None or acting_membership.member_role not in OFFICER_ROLES:
            raise NotAuthorizedToSchedulePayout("Only a chairperson, treasurer, or secretary of this chama can schedule a payout")
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


class ListContributions:
    """Viewing a member's contribution history is not the sensitive action
    (recording one is) -- any member of the *same* chama can view it, not
    just officers. Still gated on chama membership so an unrelated
    authenticated user can't browse a chama they don't belong to."""

    def __init__(self, contribution_repo: ChamaContributionRepository, member_repo: ChamaMemberRepository):
        self.contribution_repo = contribution_repo
        self.member_repo = member_repo

    async def execute(self, *, member_id: str, requesting_user_id: str, limit: int, offset: int) -> tuple[list[ChamaContribution], int]:
        target_member = await self.member_repo.get(member_id)
        if target_member is None:
            raise MemberNotFound(member_id)
        requester_membership = await self.member_repo.get_for_user(target_member.chama_id, requesting_user_id)
        if requester_membership is None:
            raise NotAMemberOfThisChama(target_member.chama_id)
        return await self.contribution_repo.list_for_member(member_id, limit, offset)


class ListPayouts:
    def __init__(self, payout_repo: ChamaPayoutRepository, member_repo: ChamaMemberRepository):
        self.payout_repo = payout_repo
        self.member_repo = member_repo

    async def execute(self, *, chama_id: str, requesting_user_id: str, limit: int, offset: int) -> tuple[list[ChamaPayout], int]:
        requester_membership = await self.member_repo.get_for_user(chama_id, requesting_user_id)
        if requester_membership is None:
            raise NotAMemberOfThisChama(chama_id)
        return await self.payout_repo.list_for_chama(chama_id, limit, offset)
