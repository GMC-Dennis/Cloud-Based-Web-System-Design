import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chama.domain.entities import ChamaContribution, ChamaGroup, ChamaMember, ChamaPayout
from app.modules.chama.infrastructure.models import ChamaContribution as ContributionModel
from app.modules.chama.infrastructure.models import ChamaGroup as GroupModel
from app.modules.chama.infrastructure.models import ChamaMember as MemberModel
from app.modules.chama.infrastructure.models import ChamaPayout as PayoutModel


def _to_group(row: GroupModel) -> ChamaGroup:
    return ChamaGroup(id=str(row.id), group_name=row.group_name, contribution_cycle=row.contribution_cycle, cycle_amount=row.cycle_amount, created_at=row.created_at)


def _to_member(row: MemberModel) -> ChamaMember:
    return ChamaMember(id=str(row.id), chama_id=str(row.chama_id), user_id=str(row.user_id), member_role=row.member_role, joined_at=row.joined_at)


def _to_contribution(row: ContributionModel) -> ChamaContribution:
    return ChamaContribution(
        id=str(row.id), chama_id=str(row.chama_id), member_id=str(row.member_id), cycle_due_date=row.cycle_due_date,
        amount_due=row.amount_due, amount_paid=row.amount_paid, paid_at=row.paid_at, is_on_time=row.is_on_time,
    )


def _to_payout(row: PayoutModel) -> ChamaPayout:
    return ChamaPayout(
        id=str(row.id), chama_id=str(row.chama_id), recipient_member_id=str(row.recipient_member_id),
        payout_amount=row.payout_amount, scheduled_date=row.scheduled_date, paid_out_at=row.paid_out_at,
    )


class SqlChamaGroupRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, *, group_name: str, contribution_cycle: str, cycle_amount: Decimal) -> ChamaGroup:
        row = GroupModel(group_name=group_name, contribution_cycle=contribution_cycle, cycle_amount=cycle_amount)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _to_group(row)

    async def get(self, chama_id: str) -> ChamaGroup | None:
        row = await self.session.get(GroupModel, uuid.UUID(chama_id))
        return _to_group(row) if row else None

    async def list_for_user(self, user_id: str, limit: int, offset: int) -> tuple[list[ChamaGroup], int]:
        base = select(GroupModel).join(MemberModel, MemberModel.chama_id == GroupModel.id).where(MemberModel.user_id == uuid.UUID(user_id))
        total = (await self.session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        rows = (await self.session.execute(base.order_by(GroupModel.created_at.desc(), GroupModel.id).limit(limit).offset(offset))).scalars()
        return [_to_group(r) for r in rows], total


class SqlChamaMemberRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, *, chama_id: str, user_id: str, member_role: str) -> ChamaMember:
        row = MemberModel(chama_id=uuid.UUID(chama_id), user_id=uuid.UUID(user_id), member_role=member_role)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _to_member(row)

    async def get(self, member_id: str) -> ChamaMember | None:
        row = await self.session.get(MemberModel, uuid.UUID(member_id))
        return _to_member(row) if row else None

    async def get_for_user(self, chama_id: str, user_id: str) -> ChamaMember | None:
        row = (
            await self.session.execute(
                select(MemberModel).where(MemberModel.chama_id == uuid.UUID(chama_id), MemberModel.user_id == uuid.UUID(user_id))
            )
        ).scalar_one_or_none()
        return _to_member(row) if row else None

    async def list_for_chama(self, chama_id: str, limit: int, offset: int) -> tuple[list[ChamaMember], int]:
        total = (
            await self.session.execute(select(func.count()).select_from(MemberModel).where(MemberModel.chama_id == uuid.UUID(chama_id)))
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(MemberModel)
                .where(MemberModel.chama_id == uuid.UUID(chama_id))
                .order_by(MemberModel.joined_at.desc(), MemberModel.id)
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
        return [_to_member(r) for r in rows], total

    async def list_for_user(self, user_id: str) -> list[ChamaMember]:
        rows = (await self.session.execute(select(MemberModel).where(MemberModel.user_id == uuid.UUID(user_id)))).scalars()
        return [_to_member(r) for r in rows]


class SqlChamaContributionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(
        self, *, chama_id: str, member_id: str, cycle_due_date: date, amount_due: Decimal, amount_paid: Decimal, paid_at: datetime, is_on_time: bool
    ) -> ChamaContribution:
        row = ContributionModel(
            chama_id=uuid.UUID(chama_id), member_id=uuid.UUID(member_id), cycle_due_date=cycle_due_date,
            amount_due=amount_due, amount_paid=amount_paid, paid_at=paid_at, is_on_time=is_on_time,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _to_contribution(row)

    async def punctuality(self, member_id: str) -> float:
        result = await self.session.execute(
            select(
                func.count().filter(ContributionModel.is_on_time.is_(True)),
                func.count().filter(ContributionModel.is_on_time.is_not(None)),
            ).where(ContributionModel.member_id == uuid.UUID(member_id))
        )
        on_time, total = result.one()
        if not total:
            return 0.0
        return (on_time / total) * 100.0

    async def list_for_member(self, member_id: str, limit: int, offset: int) -> tuple[list[ChamaContribution], int]:
        total = (
            await self.session.execute(select(func.count()).select_from(ContributionModel).where(ContributionModel.member_id == uuid.UUID(member_id)))
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(ContributionModel)
                .where(ContributionModel.member_id == uuid.UUID(member_id))
                .order_by(ContributionModel.cycle_due_date.desc(), ContributionModel.id)
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
        return [_to_contribution(r) for r in rows], total


class SqlChamaPayoutRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def schedule(self, *, chama_id: str, recipient_member_id: str, payout_amount: Decimal, scheduled_date: date) -> ChamaPayout:
        row = PayoutModel(chama_id=uuid.UUID(chama_id), recipient_member_id=uuid.UUID(recipient_member_id), payout_amount=payout_amount, scheduled_date=scheduled_date)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _to_payout(row)

    async def list_for_chama(self, chama_id: str, limit: int, offset: int) -> tuple[list[ChamaPayout], int]:
        total = (
            await self.session.execute(select(func.count()).select_from(PayoutModel).where(PayoutModel.chama_id == uuid.UUID(chama_id)))
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(PayoutModel)
                .where(PayoutModel.chama_id == uuid.UUID(chama_id))
                .order_by(PayoutModel.scheduled_date.asc(), PayoutModel.id)
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
        return [_to_payout(r) for r in rows], total
