from decimal import Decimal

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.modules.ledger.infrastructure.repository import SqlInventoryRepository, SqlProductRepository


async def test_movement_updates_quantity_on_hand(db_session, test_user):
    product_repo = SqlProductRepository(db_session)
    inventory_repo = SqlInventoryRepository(db_session)

    product = await product_repo.create(merchant_id=test_user.id, name="Sugar 1kg", unit_cost=Decimal("100"), unit_price=Decimal("130"), reorder_threshold=5)
    assert product.quantity_on_hand == 0

    await inventory_repo.record_movement(product_id=product.id, duka_transaction_id=None, quantity_delta=50)
    await db_session.flush()

    refreshed = await product_repo.get(product.id)
    assert refreshed.quantity_on_hand == 50

    await inventory_repo.record_movement(product_id=product.id, duka_transaction_id=None, quantity_delta=-20)
    await db_session.flush()

    refreshed = await product_repo.get(product.id)
    assert refreshed.quantity_on_hand == 30


async def test_movement_cannot_oversell_below_zero(db_session, test_user):
    product_repo = SqlProductRepository(db_session)
    inventory_repo = SqlInventoryRepository(db_session)

    product = await product_repo.create(merchant_id=test_user.id, name="Rice 2kg", unit_cost=Decimal("150"), unit_price=Decimal("200"), reorder_threshold=5)
    await inventory_repo.record_movement(product_id=product.id, duka_transaction_id=None, quantity_delta=10)
    await db_session.flush()

    with pytest.raises((IntegrityError, DBAPIError)):
        await inventory_repo.record_movement(product_id=product.id, duka_transaction_id=None, quantity_delta=-11)
        await db_session.flush()
