from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.modules.chama.application.exceptions import CannotRecordOwnContribution, NotAuthorizedToRecordContribution
from app.modules.chama.application.use_cases import RecordContribution
from app.modules.chama.infrastructure.repository import (
    SqlChamaContributionRepository,
    SqlChamaGroupRepository,
    SqlChamaMemberRepository,
)
from app.modules.identity.infrastructure.repository import SqlUserRepository


async def _make_chama_with_officer_and_member(db_session):
    group = await SqlChamaGroupRepository(db_session).create(group_name="Duty Test Chama", contribution_cycle="MONTHLY", cycle_amount=Decimal("1000"))

    officer_user = await SqlUserRepository(db_session).create(phone_number="+254788000001", full_name="Treasurer", role="MERCHANT")
    plain_user = await SqlUserRepository(db_session).create(phone_number="+254788000002", full_name="Plain Member", role="MERCHANT")
    target_user = await SqlUserRepository(db_session).create(phone_number="+254788000003", full_name="Target Member", role="MERCHANT")

    member_repo = SqlChamaMemberRepository(db_session)
    officer = await member_repo.add(chama_id=group.id, user_id=officer_user.id, member_role="TREASURER")
    plain_member = await member_repo.add(chama_id=group.id, user_id=plain_user.id, member_role="MEMBER")
    target_member = await member_repo.add(chama_id=group.id, user_id=target_user.id, member_role="MEMBER")

    await db_session.flush()
    return group, officer, plain_member, target_member


async def test_officer_can_record_another_members_contribution(db_session):
    group, officer, _, target_member = await _make_chama_with_officer_and_member(db_session)

    contribution = await RecordContribution(SqlChamaContributionRepository(db_session), SqlChamaMemberRepository(db_session)).execute(
        chama_id=group.id,
        member_id=target_member.id,
        cycle_due_date=date(2026, 8, 1),
        amount_due=Decimal("1000"),
        amount_paid=Decimal("1000"),
        paid_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        target_user_id=target_member.user_id,
        recorded_by_user_id=officer.user_id,
    )
    assert contribution.is_on_time is True


async def test_member_cannot_record_their_own_contribution(db_session):
    group, officer, _, target_member = await _make_chama_with_officer_and_member(db_session)

    with pytest.raises(CannotRecordOwnContribution):
        await RecordContribution(SqlChamaContributionRepository(db_session), SqlChamaMemberRepository(db_session)).execute(
            chama_id=group.id,
            member_id=target_member.id,
            cycle_due_date=date(2026, 8, 1),
            amount_due=Decimal("1000"),
            amount_paid=Decimal("1000"),
            paid_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            target_user_id=target_member.user_id,
            recorded_by_user_id=target_member.user_id,  # same person as the member being credited
        )


async def test_plain_member_cannot_record_someone_elses_contribution(db_session):
    # Only an officer (CHAIRPERSON/TREASURER/SECRETARY) can attest to
    # someone else's payment -- a plain MEMBER can't either, even though
    # they're not self-recording.
    group, _, plain_member, target_member = await _make_chama_with_officer_and_member(db_session)

    with pytest.raises(NotAuthorizedToRecordContribution):
        await RecordContribution(SqlChamaContributionRepository(db_session), SqlChamaMemberRepository(db_session)).execute(
            chama_id=group.id,
            member_id=target_member.id,
            cycle_due_date=date(2026, 8, 1),
            amount_due=Decimal("1000"),
            amount_paid=Decimal("1000"),
            paid_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            target_user_id=target_member.user_id,
            recorded_by_user_id=plain_member.user_id,
        )


async def test_non_member_of_this_chama_cannot_record_a_contribution(db_session):
    group, _, _, target_member = await _make_chama_with_officer_and_member(db_session)
    outsider = await SqlUserRepository(db_session).create(phone_number="+254788000099", full_name="Outsider", role="MERCHANT")

    with pytest.raises(NotAuthorizedToRecordContribution):
        await RecordContribution(SqlChamaContributionRepository(db_session), SqlChamaMemberRepository(db_session)).execute(
            chama_id=group.id,
            member_id=target_member.id,
            cycle_due_date=date(2026, 8, 1),
            amount_due=Decimal("1000"),
            amount_paid=Decimal("1000"),
            paid_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            target_user_id=target_member.user_id,
            recorded_by_user_id=outsider.id,
        )
