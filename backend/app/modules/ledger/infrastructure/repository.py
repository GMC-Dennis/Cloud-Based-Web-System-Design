import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ledger.domain.entities import DukaTransaction, InventoryMovement, Product
from app.modules.ledger.infrastructure.models import DukaTransaction as TxnModel
from app.modules.ledger.infrastructure.models import InventoryMovement as MovementModel
from app.modules.ledger.infrastructure.models import Product as ProductModel


def _to_domain_txn(row: TxnModel) -> DukaTransaction:
    return DukaTransaction(
        id=str(row.id),
        merchant_id=str(row.merchant_id),
        sequence_no=row.sequence_no,
        amount=row.amount,
        currency=row.currency,
        transaction_type=row.transaction_type,
        is_credit=row.is_credit,
        customer_phone=row.customer_phone,
        previous_hash=row.previous_hash,
        record_hash=row.record_hash,
        created_at=row.created_at,
    )


def _to_domain_product(row: ProductModel) -> Product:
    return Product(
        id=str(row.id),
        merchant_id=str(row.merchant_id),
        name=row.name,
        unit_cost=row.unit_cost,
        unit_price=row.unit_price,
        quantity_on_hand=row.quantity_on_hand,
        reorder_threshold=row.reorder_threshold,
        updated_at=row.updated_at,
    )


class SqlLedgerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_last_transaction(self, merchant_id: str) -> DukaTransaction | None:
        row = (
            await self.session.execute(
                select(TxnModel)
                .where(TxnModel.merchant_id == uuid.UUID(merchant_id))
                .order_by(TxnModel.sequence_no.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return _to_domain_txn(row) if row else None

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
    ) -> DukaTransaction:
        row = TxnModel(
            merchant_id=uuid.UUID(merchant_id),
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
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _to_domain_txn(row)

    async def list_for_merchant(self, merchant_id: str, limit: int, offset: int) -> tuple[list[DukaTransaction], int]:
        total = (
            await self.session.execute(
                select(func.count()).select_from(TxnModel).where(TxnModel.merchant_id == uuid.UUID(merchant_id))
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(TxnModel)
                .where(TxnModel.merchant_id == uuid.UUID(merchant_id))
                .order_by(TxnModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
        return [_to_domain_txn(r) for r in rows], total

    async def sales_total_since(self, merchant_id: str, since: datetime) -> Decimal:
        result = await self.session.execute(
            select(func.coalesce(func.sum(TxnModel.amount), 0)).where(
                TxnModel.merchant_id == uuid.UUID(merchant_id),
                TxnModel.transaction_type == "SALE",
                TxnModel.created_at >= since,
            )
        )
        return Decimal(result.scalar_one())

    async def avg_receivables_days(self, merchant_id: str) -> float:
        # Proxy metric: the schema doesn't track credit-sale repayment explicitly
        # (no "this SALE settles that earlier credit SALE" link), so a credit
        # transaction is treated as "collected" by the next transaction from the
        # same customer_phone, or still outstanding (measured to now) if none exists.
        result = await self.session.execute(
            text(
                """
                SELECT AVG(
                    EXTRACT(EPOCH FROM (
                        COALESCE(
                            (SELECT MIN(t2.created_at) FROM duka_transactions t2
                             WHERE t2.customer_phone = t1.customer_phone
                               AND t2.merchant_id = t1.merchant_id
                               AND t2.created_at > t1.created_at),
                            CURRENT_TIMESTAMP
                        ) - t1.created_at
                    )) / 86400.0
                ) AS avg_days
                FROM duka_transactions t1
                WHERE t1.merchant_id = :merchant_id
                  AND t1.is_credit = TRUE
                  AND t1.customer_phone IS NOT NULL
                """
            ),
            {"merchant_id": merchant_id},
        )
        avg_days = result.scalar_one_or_none()
        return float(avg_days) if avg_days is not None else 0.0

    async def active_business_days_since(self, merchant_id: str, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count(func.distinct(func.date(TxnModel.created_at)))).where(
                TxnModel.merchant_id == uuid.UUID(merchant_id),
                TxnModel.transaction_type == "SALE",
                TxnModel.created_at >= since,
            )
        )
        return result.scalar_one()


class SqlProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, *, merchant_id: str, name: str, unit_cost: Decimal, unit_price: Decimal, reorder_threshold: int) -> Product:
        row = ProductModel(
            merchant_id=uuid.UUID(merchant_id), name=name, unit_cost=unit_cost, unit_price=unit_price, reorder_threshold=reorder_threshold
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _to_domain_product(row)

    async def get(self, product_id: str) -> Product | None:
        row = await self.session.get(ProductModel, uuid.UUID(product_id))
        return _to_domain_product(row) if row else None

    async def list_for_merchant(self, merchant_id: str, limit: int, offset: int) -> tuple[list[Product], int]:
        total = (
            await self.session.execute(
                select(func.count()).select_from(ProductModel).where(ProductModel.merchant_id == uuid.UUID(merchant_id))
            )
        ).scalar_one()
        rows = (
            await self.session.execute(
                select(ProductModel)
                .where(ProductModel.merchant_id == uuid.UUID(merchant_id))
                .order_by(ProductModel.updated_at.desc(), ProductModel.id)
                .limit(limit)
                .offset(offset)
            )
        ).scalars()
        return [_to_domain_product(r) for r in rows], total

    async def margin_stability(self, merchant_id: str, since: datetime) -> float:
        # Windowed to `since` (v1.5) -- previously all-time, which let a
        # single burst of fabricated high-margin sales permanently distort
        # this feature instead of decaying as real transaction volume
        # accumulates, the same rolling window sales_velocity already uses.
        result = await self.session.execute(
            text(
                """
                SELECT
                    SUM((p.unit_price - p.unit_cost) * ABS(im.quantity_delta)) AS gross_profit,
                    SUM(p.unit_price * ABS(im.quantity_delta)) AS revenue
                FROM inventory_movements im
                JOIN products p ON p.id = im.product_id
                WHERE p.merchant_id = :merchant_id AND im.quantity_delta < 0 AND im.created_at >= :since
                """
            ),
            {"merchant_id": merchant_id, "since": since},
        )
        row = result.one()
        gross_profit, revenue = row.gross_profit, row.revenue
        if not revenue:
            return 0.0
        return float(gross_profit) / float(revenue)


class SqlInventoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_movement(self, *, product_id: str, duka_transaction_id: str | None, quantity_delta: int) -> InventoryMovement:
        row = MovementModel(
            product_id=uuid.UUID(product_id),
            duka_transaction_id=uuid.UUID(duka_transaction_id) if duka_transaction_id else None,
            quantity_delta=quantity_delta,
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return InventoryMovement(
            id=str(row.id),
            product_id=str(row.product_id),
            duka_transaction_id=str(row.duka_transaction_id) if row.duka_transaction_id else None,
            quantity_delta=row.quantity_delta,
            created_at=row.created_at,
        )
