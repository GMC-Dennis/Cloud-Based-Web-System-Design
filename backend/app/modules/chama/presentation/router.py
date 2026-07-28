from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.db import get_db
from app.core.deps import CurrentUser, get_current_user
from app.modules.chama.application.use_cases import (
    AddMember,
    CreateChama,
    GetPunctuality,
    ListMembers,
    ListMyChamas,
    RecordContribution,
    SchedulePayout,
)
from app.modules.chama.infrastructure.repository import (
    SqlChamaContributionRepository,
    SqlChamaGroupRepository,
    SqlChamaMemberRepository,
    SqlChamaPayoutRepository,
)
from app.modules.chama.presentation.schemas import (
    AddMemberIn,
    ChamaGroupOut,
    ChamaMemberOut,
    ContributionOut,
    CreateChamaIn,
    PayoutOut,
    PunctualityOut,
    RecordContributionIn,
    SchedulePayoutIn,
)

router = APIRouter(prefix="/chama", tags=["chama"])


@router.post("/groups", response_model=ChamaGroupOut)
async def create_chama(body: CreateChamaIn, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> ChamaGroupOut:
    group = await CreateChama(SqlChamaGroupRepository(db), SqlChamaMemberRepository(db)).execute(
        group_name=body.group_name, contribution_cycle=body.contribution_cycle, cycle_amount=body.cycle_amount, creator_user_id=user.id
    )
    await db.commit()
    return ChamaGroupOut(**group.__dict__)


@router.get("/groups", response_model=list[ChamaGroupOut])
async def list_my_chamas(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> list[ChamaGroupOut]:
    groups = await ListMyChamas(SqlChamaGroupRepository(db)).execute(user.id)
    return [ChamaGroupOut(**g.__dict__) for g in groups]


@router.post("/groups/{chama_id}/members", response_model=ChamaMemberOut)
async def add_member(chama_id: str, body: AddMemberIn, db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(get_current_user)) -> ChamaMemberOut:
    member = await AddMember(SqlChamaMemberRepository(db)).execute(chama_id=chama_id, user_id=body.user_id, member_role=body.member_role)
    await db.commit()
    return ChamaMemberOut(**member.__dict__)


@router.get("/groups/{chama_id}/members", response_model=list[ChamaMemberOut])
async def list_members(chama_id: str, db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(get_current_user)) -> list[ChamaMemberOut]:
    members = await ListMembers(SqlChamaMemberRepository(db)).execute(chama_id)
    return [ChamaMemberOut(**m.__dict__) for m in members]


@router.post("/contributions", response_model=ContributionOut)
async def record_contribution(body: RecordContributionIn, db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(get_current_user)) -> ContributionOut:
    member_repo = SqlChamaMemberRepository(db)
    member = await member_repo.get(body.member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such chama member")

    contribution = await RecordContribution(SqlChamaContributionRepository(db), get_redis()).execute(
        chama_id=member.chama_id,
        member_id=body.member_id,
        cycle_due_date=body.cycle_due_date,
        amount_due=body.amount_due,
        amount_paid=body.amount_paid,
        paid_at=body.paid_at,
        user_id=member.user_id,
    )
    await db.commit()
    return ContributionOut(**contribution.__dict__)


@router.get("/members/{member_id}/punctuality", response_model=PunctualityOut)
async def get_punctuality(member_id: str, db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(get_current_user)) -> PunctualityOut:
    pct = await GetPunctuality(SqlChamaContributionRepository(db)).execute(member_id)
    return PunctualityOut(member_id=member_id, punctuality_pct=pct)


@router.post("/payouts", response_model=PayoutOut)
async def schedule_payout(body: SchedulePayoutIn, chama_id: str, db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(get_current_user)) -> PayoutOut:
    payout = await SchedulePayout(SqlChamaPayoutRepository(db)).execute(
        chama_id=chama_id, recipient_member_id=body.recipient_member_id, payout_amount=body.payout_amount, scheduled_date=body.scheduled_date
    )
    await db.commit()
    return PayoutOut(**payout.__dict__)
