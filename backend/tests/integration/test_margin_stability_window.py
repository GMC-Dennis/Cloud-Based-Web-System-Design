from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.modules.ledger.infrastructure.models import InventoryMovement
from app.modules.ledger.infrastructure.repository import SqlProductRepository


async def _create_product(db_session, merchant_id: str, unit_cost: str, unit_price: str) -> str:
    product = await SqlProductRepository(db_session).create(
        merchant_id=merchant_id, name="Windowed Product", unit_cost=Decimal(unit_cost), unit_price=Decimal(unit_price), reorder_threshold=0
    )
    await db_session.flush()
    return product.id


async def _insert_movement_at(db_session, product_id: str, quantity_delta: int, created_at: datetime) -> None:
    row = InventoryMovement(product_id=product_id, duka_transaction_id=None, quantity_delta=quantity_delta, created_at=created_at)
    db_session.add(row)
    await db_session.flush()


async def test_margin_stability_excludes_movements_outside_the_window(db_session, test_user):
    # High-margin product: unit_cost=10, unit_price=100 -> 90% margin.
    product_id = await _create_product(db_session, test_user.id, "10", "100")
    product_repo = SqlProductRepository(db_session)

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=30)

    # Stock the shelf, then a large sale from 60 days ago -- outside the window.
    await _insert_movement_at(db_session, product_id, 200, now - timedelta(days=90))
    await _insert_movement_at(db_session, product_id, -100, now - timedelta(days=60))

    # No movement inside the window yet -> no revenue, so margin_stability is 0.
    assert await product_repo.margin_stability(test_user.id, since) == 0.0

    # A small recent sale inside the window -- this is what should actually count.
    await _insert_movement_at(db_session, product_id, -1, now - timedelta(days=1))

    margin = await product_repo.margin_stability(test_user.id, since)
    assert margin == pytest.approx(0.9)  # (100-10)/100, unaffected by the old out-of-window sale


async def test_margin_stability_includes_all_movements_within_the_window(db_session, test_user):
    product_id = await _create_product(db_session, test_user.id, "10", "100")
    product_repo = SqlProductRepository(db_session)

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=30)

    await _insert_movement_at(db_session, product_id, 20, now - timedelta(days=20))
    await _insert_movement_at(db_session, product_id, -5, now - timedelta(days=5))
    await _insert_movement_at(db_session, product_id, -5, now - timedelta(days=10))

    margin = await product_repo.margin_stability(test_user.id, since)
    assert margin == pytest.approx(0.9)
