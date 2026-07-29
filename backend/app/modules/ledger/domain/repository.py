from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.modules.ledger.domain.entities import DukaTransaction, InventoryMovement, Product


class LedgerRepository(Protocol):
    async def acquire_merchant_lock(self, merchant_id: str) -> None:
        """Postgres advisory transaction lock keyed on merchant_id -- serializes
        concurrent duka_transactions appends for the *same* merchant so two
        simultaneous requests can't both read the same "last sequence_no"
        before either commits. Auto-releases at transaction end (commit or
        rollback); no explicit unlock needed. Different merchants are
        unaffected -- see _AppendLedgerEntry for why this is called first."""
        ...
    async def get_last_transaction(self, merchant_id: str) -> DukaTransaction | None: ...
    async def append(
        self,
        *,
        merchant_id: str,
        sequence_no: int,
        amount: Decimal,
        currency: str,
        transaction_type: str,
        is_credit: bool,
        customer_phone: str | None,
        previous_hash: str,
        record_hash: str,
        created_at: datetime,
    ) -> DukaTransaction: ...
    async def list_for_merchant(self, merchant_id: str, limit: int, offset: int) -> tuple[list[DukaTransaction], int]: ...
    async def sales_total_since(self, merchant_id: str, since: datetime) -> Decimal: ...
    async def avg_receivables_days(self, merchant_id: str) -> float: ...
    async def active_business_days_since(self, merchant_id: str, since: datetime) -> int: ...


class ProductRepository(Protocol):
    async def create(self, *, merchant_id: str, name: str, unit_cost: Decimal, unit_price: Decimal, reorder_threshold: int) -> Product: ...
    async def get(self, product_id: str) -> Product | None: ...
    async def list_for_merchant(self, merchant_id: str, limit: int, offset: int) -> tuple[list[Product], int]: ...
    async def margin_stability(self, merchant_id: str, since: datetime) -> float: ...
    async def daily_margin_ratios(self, merchant_id: str, since: datetime) -> list[float]:
        """Per-day gross_profit/revenue ratio across days with at least one
        sale movement in the window -- used only for the anomaly-flag
        heuristic (platform-cross-cutting spec §3.4d, "implausibly smooth
        margin"), not fed into the scoring model like margin_stability is."""
        ...


class InventoryRepository(Protocol):
    async def record_movement(
        self, *, product_id: str, duka_transaction_id: str | None, quantity_delta: int
    ) -> InventoryMovement: ...
