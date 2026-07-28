from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.modules.ledger.infrastructure.models import DukaTransaction


async def _insert_raw(db_session, *, merchant_id, sequence_no, previous_hash, record_hash="a" * 64):
    row = DukaTransaction(
        merchant_id=merchant_id,
        sequence_no=sequence_no,
        amount=Decimal("100.00"),
        currency="KES",
        transaction_type="SALE",
        is_credit=False,
        customer_phone=None,
        previous_hash=previous_hash,
        record_hash=record_hash,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def test_genesis_row_with_correct_previous_hash_succeeds(db_session, test_user):
    genesis = "0" * 64
    row = await _insert_raw(db_session, merchant_id=test_user.id, sequence_no=1, previous_hash=genesis)
    assert row.id is not None


async def test_genesis_row_with_wrong_previous_hash_is_rejected(db_session, test_user):
    with pytest.raises((IntegrityError, DBAPIError)):
        await _insert_raw(db_session, merchant_id=test_user.id, sequence_no=1, previous_hash="f" * 64)


async def test_second_row_must_chain_to_first_records_hash(db_session, test_user):
    genesis = "0" * 64
    first = await _insert_raw(db_session, merchant_id=test_user.id, sequence_no=1, previous_hash=genesis, record_hash="b" * 64)
    await db_session.flush()

    # Correct chain link succeeds.
    second = await _insert_raw(db_session, merchant_id=test_user.id, sequence_no=2, previous_hash=first.record_hash)
    assert second.id is not None


async def test_broken_chain_link_is_rejected(db_session, test_user):
    genesis = "0" * 64
    await _insert_raw(db_session, merchant_id=test_user.id, sequence_no=1, previous_hash=genesis, record_hash="b" * 64)
    await db_session.flush()

    with pytest.raises((IntegrityError, DBAPIError)):
        # Wrong previous_hash -- doesn't match the row at sequence_no=1.
        await _insert_raw(db_session, merchant_id=test_user.id, sequence_no=2, previous_hash="c" * 64)


async def test_sequence_gap_is_rejected(db_session, test_user):
    genesis = "0" * 64
    with pytest.raises((IntegrityError, DBAPIError)):
        # Jumping straight to sequence_no=2 with no row at sequence_no=1.
        await _insert_raw(db_session, merchant_id=test_user.id, sequence_no=2, previous_hash=genesis)


async def test_update_is_rejected_by_append_only_trigger(db_session, test_user):
    from sqlalchemy import update

    genesis = "0" * 64
    row = await _insert_raw(db_session, merchant_id=test_user.id, sequence_no=1, previous_hash=genesis)
    await db_session.flush()

    with pytest.raises((IntegrityError, DBAPIError)):
        await db_session.execute(update(DukaTransaction).where(DukaTransaction.id == row.id).values(amount=Decimal("1.00")))
        await db_session.flush()


async def test_delete_is_rejected_by_append_only_trigger(db_session, test_user):
    from sqlalchemy import delete

    genesis = "0" * 64
    row = await _insert_raw(db_session, merchant_id=test_user.id, sequence_no=1, previous_hash=genesis)
    await db_session.flush()

    with pytest.raises((IntegrityError, DBAPIError)):
        await db_session.execute(delete(DukaTransaction).where(DukaTransaction.id == row.id))
        await db_session.flush()
