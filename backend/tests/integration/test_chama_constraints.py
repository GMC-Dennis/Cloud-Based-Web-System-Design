from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.chama.infrastructure.repository import (
    SqlChamaContributionRepository,
    SqlChamaGroupRepository,
    SqlChamaMemberRepository,
)


async def _make_member(db_session, user_id):
    group = await SqlChamaGroupRepository(db_session).create(group_name="Umoja Chama", contribution_cycle="MONTHLY", cycle_amount=Decimal("1000"))
    member = await SqlChamaMemberRepository(db_session).add(chama_id=group.id, user_id=user_id, member_role="MEMBER")
    await db_session.flush()
    return group, member


async def test_duplicate_contribution_for_same_cycle_is_rejected(db_session, test_user):
    group, member = await _make_member(db_session, test_user.id)
    contribution_repo = SqlChamaContributionRepository(db_session)
    due_date = date(2026, 8, 1)

    await contribution_repo.record(
        chama_id=group.id, member_id=member.id, cycle_due_date=due_date, amount_due=Decimal("1000"), amount_paid=Decimal("1000"),
        paid_at=datetime.now(timezone.utc), is_on_time=True,
    )
    await db_session.flush()

    with pytest.raises(IntegrityError):
        await contribution_repo.record(
            chama_id=group.id, member_id=member.id, cycle_due_date=due_date, amount_due=Decimal("1000"), amount_paid=Decimal("1000"),
            paid_at=datetime.now(timezone.utc), is_on_time=True,
        )
        await db_session.flush()


async def test_punctuality_reflects_on_time_ratio(db_session, test_user):
    group, member = await _make_member(db_session, test_user.id)
    contribution_repo = SqlChamaContributionRepository(db_session)

    # 2 on-time, 1 late out of 3.
    await contribution_repo.record(chama_id=group.id, member_id=member.id, cycle_due_date=date(2026, 1, 1), amount_due=Decimal("1000"), amount_paid=Decimal("1000"), paid_at=datetime(2026, 1, 1, tzinfo=timezone.utc), is_on_time=True)
    await contribution_repo.record(chama_id=group.id, member_id=member.id, cycle_due_date=date(2026, 2, 1), amount_due=Decimal("1000"), amount_paid=Decimal("1000"), paid_at=datetime(2026, 2, 1, tzinfo=timezone.utc), is_on_time=True)
    await contribution_repo.record(chama_id=group.id, member_id=member.id, cycle_due_date=date(2026, 3, 1), amount_due=Decimal("1000"), amount_paid=Decimal("1000"), paid_at=datetime(2026, 3, 5, tzinfo=timezone.utc), is_on_time=False)
    await db_session.flush()

    pct = await contribution_repo.punctuality(member.id)
    assert pct == pytest.approx(200 / 3)
