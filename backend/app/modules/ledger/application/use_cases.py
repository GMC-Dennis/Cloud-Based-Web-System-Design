from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from redis.asyncio import Redis

from app.core.cache import invalidate_score_cache
from app.modules.ledger.application.exceptions import ProductNotOwnedByMerchant, SaleRequiresLineItems
from app.modules.ledger.domain.entities import DukaTransaction, Product
from app.modules.ledger.domain.hashing import GENESIS_HASH, compute_record_hash
from app.modules.ledger.domain.repository import InventoryRepository, LedgerRepository, ProductRepository


@dataclass
class SaleLineItem:
    product_id: str
    quantity: int


class _AppendLedgerEntry:
    """Shared by all three transaction-recording use cases below -- every
    write to duka_transactions, regardless of type, shares one per-merchant
    hash chain and sequence counter."""

    def __init__(self, ledger_repo: LedgerRepository):
        self.ledger_repo = ledger_repo

    async def execute(
        self, *, merchant_id: str, amount: Decimal, currency: str, transaction_type: str, is_credit: bool, customer_phone: str | None
    ) -> DukaTransaction:
        last = await self.ledger_repo.get_last_transaction(merchant_id)
        sequence_no = (last.sequence_no + 1) if last else 1
        previous_hash = last.record_hash if last else GENESIS_HASH
        created_at = datetime.now(timezone.utc)
        record_hash = compute_record_hash(
            previous_hash=previous_hash, merchant_id=merchant_id, sequence_no=sequence_no, amount=amount, currency=currency, created_at=created_at
        )
        return await self.ledger_repo.append(
            merchant_id=merchant_id,
            sequence_no=sequence_no,
            amount=amount,
            currency=currency,
            transaction_type=transaction_type,
            is_credit=is_credit,
            customer_phone=customer_phone,
            previous_hash=previous_hash,
            record_hash=record_hash,
            created_at=created_at,
        )


class RecordSale:
    def __init__(
        self, ledger_repo: LedgerRepository, inventory_repo: InventoryRepository, product_repo: ProductRepository, redis: Redis | None = None
    ):
        self._append = _AppendLedgerEntry(ledger_repo)
        self.inventory_repo = inventory_repo
        self.product_repo = product_repo
        self.redis = redis

    async def execute(
        self,
        *,
        merchant_id: str,
        amount: Decimal,
        currency: str = "KES",
        is_credit: bool = False,
        customer_phone: str | None = None,
        line_items: list[SaleLineItem] | None = None,
    ) -> DukaTransaction:
        line_items = line_items or []
        if not line_items:
            raise SaleRequiresLineItems("A sale must reference at least one product line item")

        for item in line_items:
            product = await self.product_repo.get(item.product_id)
            if product is None or product.merchant_id != merchant_id:
                raise ProductNotOwnedByMerchant(f"Product {item.product_id} does not belong to this merchant")

        # Validated before anything is written -- a rejected sale should
        # never touch the hash chain at all, not rely on a rollback to undo it.
        txn = await self._append.execute(
            merchant_id=merchant_id, amount=amount, currency=currency, transaction_type="SALE", is_credit=is_credit, customer_phone=customer_phone
        )
        for item in line_items:
            await self.inventory_repo.record_movement(
                product_id=item.product_id, duka_transaction_id=txn.id, quantity_delta=-item.quantity
            )
        if self.redis is not None:
            await invalidate_score_cache(self.redis, merchant_id)
        return txn


class RecordExpense:
    def __init__(self, ledger_repo: LedgerRepository, redis: Redis | None = None):
        self._append = _AppendLedgerEntry(ledger_repo)
        self.redis = redis

    async def execute(self, *, merchant_id: str, amount: Decimal, currency: str = "KES") -> DukaTransaction:
        txn = await self._append.execute(
            merchant_id=merchant_id, amount=amount, currency=currency, transaction_type="EXPENSE", is_credit=False, customer_phone=None
        )
        if self.redis is not None:
            await invalidate_score_cache(self.redis, merchant_id)
        return txn


class RecordSupplierPayment:
    def __init__(self, ledger_repo: LedgerRepository, redis: Redis | None = None):
        self._append = _AppendLedgerEntry(ledger_repo)
        self.redis = redis

    async def execute(self, *, merchant_id: str, amount: Decimal, currency: str = "KES") -> DukaTransaction:
        txn = await self._append.execute(
            merchant_id=merchant_id, amount=amount, currency=currency, transaction_type="SUPPLIER_PAYMENT", is_credit=False, customer_phone=None
        )
        if self.redis is not None:
            await invalidate_score_cache(self.redis, merchant_id)
        return txn


class CreateProduct:
    def __init__(self, product_repo: ProductRepository):
        self.product_repo = product_repo

    async def execute(self, *, merchant_id: str, name: str, unit_cost: Decimal, unit_price: Decimal, reorder_threshold: int = 0) -> Product:
        return await self.product_repo.create(
            merchant_id=merchant_id, name=name, unit_cost=unit_cost, unit_price=unit_price, reorder_threshold=reorder_threshold
        )


class RestockProduct:
    def __init__(self, inventory_repo: InventoryRepository, product_repo: ProductRepository):
        self.inventory_repo = inventory_repo
        self.product_repo = product_repo

    async def execute(self, *, merchant_id: str, product_id: str, quantity: int):
        product = await self.product_repo.get(product_id)
        if product is None or product.merchant_id != merchant_id:
            raise ProductNotOwnedByMerchant(f"Product {product_id} does not belong to this merchant")
        return await self.inventory_repo.record_movement(product_id=product_id, duka_transaction_id=None, quantity_delta=quantity)


class ListTransactions:
    def __init__(self, ledger_repo: LedgerRepository):
        self.ledger_repo = ledger_repo

    async def execute(self, merchant_id: str, limit: int, offset: int) -> tuple[list[DukaTransaction], int]:
        return await self.ledger_repo.list_for_merchant(merchant_id, limit, offset)


class ListProducts:
    def __init__(self, product_repo: ProductRepository):
        self.product_repo = product_repo

    async def execute(self, merchant_id: str, limit: int, offset: int) -> tuple[list[Product], int]:
        return await self.product_repo.list_for_merchant(merchant_id, limit, offset)
