"""Anomaly-flag heuristic (platform-cross-cutting spec §3.4d) -- a cheap
triage signal, not a fraud model. Tests DetectAnomalyFlags directly against
raw ledger/inventory data rather than through POST /scoring/evaluate,
since that endpoint needs a trained model artifact that isn't guaranteed
to exist in the test environment.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.modules.ledger.domain.hashing import GENESIS_HASH, compute_record_hash
from app.modules.ledger.infrastructure.models import InventoryMovement
from app.modules.ledger.infrastructure.repository import SqlLedgerRepository, SqlProductRepository
from app.modules.scoring.application.use_cases import DetectAnomalyFlags


async def _insert_sale(ledger_repo, merchant_id: str, *, sequence_no: int, amount: Decimal, created_at: datetime, previous_hash: str) -> str:
    record_hash = compute_record_hash(
        previous_hash=previous_hash, merchant_id=merchant_id, sequence_no=sequence_no, amount=amount, currency="KES", created_at=created_at
    )
    txn = await ledger_repo.append(
        merchant_id=merchant_id, sequence_no=sequence_no, amount=amount, currency="KES", transaction_type="SALE",
        is_credit=False, customer_phone=None, previous_hash=previous_hash, record_hash=record_hash, created_at=created_at,
    )
    return txn.record_hash


async def _create_stocked_product(db_session, merchant_id: str, unit_cost: str, unit_price: str) -> str:
    product = await SqlProductRepository(db_session).create(
        merchant_id=merchant_id, name="Anomaly Test Product", unit_cost=Decimal(unit_cost), unit_price=Decimal(unit_price), reorder_threshold=0
    )
    await db_session.flush()
    # Stock generously, far outside any test window, so subsequent sale
    # movements never trip products.quantity_on_hand's >= 0 check.
    db_session.add(InventoryMovement(product_id=product.id, duka_transaction_id=None, quantity_delta=1000, created_at=datetime.now(timezone.utc) - timedelta(days=365)))
    await db_session.flush()
    return product.id


async def _insert_sale_movement(db_session, product_id: str, created_at: datetime) -> None:
    db_session.add(InventoryMovement(product_id=product_id, duka_transaction_id=None, quantity_delta=-1, created_at=created_at))
    await db_session.flush()


async def test_volume_spike_flag_fires_when_most_revenue_is_very_recent(db_session, test_user):
    ledger_repo = SqlLedgerRepository(db_session)
    now = datetime.now(timezone.utc)

    prev_hash = await _insert_sale(ledger_repo, test_user.id, sequence_no=1, amount=Decimal("100"), created_at=now - timedelta(days=10), previous_hash=GENESIS_HASH)
    await _insert_sale(ledger_repo, test_user.id, sequence_no=2, amount=Decimal("500"), created_at=now - timedelta(days=1), previous_hash=prev_hash)

    flags = await DetectAnomalyFlags(ledger_repo, SqlProductRepository(db_session)).execute(test_user.id)
    assert "VOLUME_SPIKE_LAST_3_DAYS" in flags


async def test_volume_spike_flag_does_not_fire_for_evenly_spread_revenue(db_session, test_user):
    ledger_repo = SqlLedgerRepository(db_session)
    now = datetime.now(timezone.utc)

    prev_hash = await _insert_sale(ledger_repo, test_user.id, sequence_no=1, amount=Decimal("500"), created_at=now - timedelta(days=20), previous_hash=GENESIS_HASH)
    await _insert_sale(ledger_repo, test_user.id, sequence_no=2, amount=Decimal("500"), created_at=now - timedelta(days=1), previous_hash=prev_hash)

    flags = await DetectAnomalyFlags(ledger_repo, SqlProductRepository(db_session)).execute(test_user.id)
    assert "VOLUME_SPIKE_LAST_3_DAYS" not in flags


async def test_smooth_margin_flag_fires_for_a_single_product_sold_across_several_days(db_session, test_user):
    # One product means every sale has an identical (price-cost)/price
    # ratio -- day-to-day variance is exactly zero. A real business selling
    # only one SKU would also trip this; that's the documented false-
    # positive tradeoff of a triage heuristic, not a bug.
    product_id = await _create_stocked_product(db_session, test_user.id, "10", "100")
    now = datetime.now(timezone.utc)
    for days_ago in (1, 5, 10):
        await _insert_sale_movement(db_session, product_id, now - timedelta(days=days_ago))

    flags = await DetectAnomalyFlags(SqlLedgerRepository(db_session), SqlProductRepository(db_session)).execute(test_user.id)
    assert "IMPLAUSIBLY_SMOOTH_MARGIN" in flags


async def test_smooth_margin_flag_does_not_fire_when_margins_vary_across_days(db_session, test_user):
    high_margin = await _create_stocked_product(db_session, test_user.id, "10", "100")  # 90% margin
    low_margin = await _create_stocked_product(db_session, test_user.id, "90", "100")  # 10% margin
    mid_margin = await _create_stocked_product(db_session, test_user.id, "50", "100")  # 50% margin
    now = datetime.now(timezone.utc)

    await _insert_sale_movement(db_session, high_margin, now - timedelta(days=1))
    await _insert_sale_movement(db_session, low_margin, now - timedelta(days=5))
    await _insert_sale_movement(db_session, mid_margin, now - timedelta(days=10))

    flags = await DetectAnomalyFlags(SqlLedgerRepository(db_session), SqlProductRepository(db_session)).execute(test_user.id)
    assert "IMPLAUSIBLY_SMOOTH_MARGIN" not in flags


async def test_no_flags_for_a_merchant_with_no_activity(db_session, test_user):
    flags = await DetectAnomalyFlags(SqlLedgerRepository(db_session), SqlProductRepository(db_session)).execute(test_user.id)
    assert flags == []
