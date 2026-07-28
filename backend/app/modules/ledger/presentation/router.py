from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.db import get_db
from app.core.deps import CurrentUser, get_current_user
from app.core.idempotency import idempotent
from app.core.pagination import Page, PageParams
from app.modules.ledger.application.use_cases import (
    CreateProduct,
    ListProducts,
    ListTransactions,
    RecordExpense,
    RecordSale,
    RecordSupplierPayment,
    RestockProduct,
    SaleLineItem,
)
from app.modules.ledger.infrastructure.repository import (
    SqlInventoryRepository,
    SqlLedgerRepository,
    SqlProductRepository,
)
from app.modules.ledger.presentation.schemas import (
    CreateProductIn,
    ProductOut,
    RecordExpenseIn,
    RecordSaleIn,
    RecordSupplierPaymentIn,
    RestockIn,
    TransactionOut,
)

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.post("/transactions/sale", response_model=TransactionOut)
async def record_sale(
    body: RecordSaleIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TransactionOut:
    async def execute() -> dict:
        use_case = RecordSale(SqlLedgerRepository(db), SqlInventoryRepository(db), get_redis())
        txn = await use_case.execute(
            merchant_id=user.id,
            amount=body.amount,
            currency=body.currency,
            is_credit=body.is_credit,
            customer_phone=body.customer_phone,
            line_items=[SaleLineItem(product_id=li.product_id, quantity=li.quantity) for li in body.line_items],
        )
        return TransactionOut(**txn.__dict__).model_dump(mode="json")

    result = await idempotent(db, user_id=user.id, idempotency_key=idempotency_key, endpoint="ledger.record_sale", execute=execute)
    await db.commit()
    return TransactionOut(**result)


@router.post("/transactions/expense", response_model=TransactionOut)
async def record_expense(
    body: RecordExpenseIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TransactionOut:
    async def execute() -> dict:
        txn = await RecordExpense(SqlLedgerRepository(db), get_redis()).execute(merchant_id=user.id, amount=body.amount, currency=body.currency)
        return TransactionOut(**txn.__dict__).model_dump(mode="json")

    result = await idempotent(db, user_id=user.id, idempotency_key=idempotency_key, endpoint="ledger.record_expense", execute=execute)
    await db.commit()
    return TransactionOut(**result)


@router.post("/transactions/supplier-payment", response_model=TransactionOut)
async def record_supplier_payment(
    body: RecordSupplierPaymentIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TransactionOut:
    async def execute() -> dict:
        txn = await RecordSupplierPayment(SqlLedgerRepository(db), get_redis()).execute(
            merchant_id=user.id, amount=body.amount, currency=body.currency
        )
        return TransactionOut(**txn.__dict__).model_dump(mode="json")

    result = await idempotent(db, user_id=user.id, idempotency_key=idempotency_key, endpoint="ledger.record_supplier_payment", execute=execute)
    await db.commit()
    return TransactionOut(**result)


@router.get("/transactions", response_model=Page[TransactionOut])
async def list_transactions(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user), page: PageParams = Depends()
) -> Page[TransactionOut]:
    txns, total = await ListTransactions(SqlLedgerRepository(db)).execute(user.id, page.limit, page.offset)
    return Page(items=[TransactionOut(**t.__dict__) for t in txns], total=total, limit=page.limit, offset=page.offset)


@router.post("/products", response_model=ProductOut)
async def create_product(body: CreateProductIn, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> ProductOut:
    product = await CreateProduct(SqlProductRepository(db)).execute(
        merchant_id=user.id, name=body.name, unit_cost=body.unit_cost, unit_price=body.unit_price, reorder_threshold=body.reorder_threshold
    )
    await db.commit()
    return ProductOut(**product.__dict__)


@router.get("/products", response_model=Page[ProductOut])
async def list_products(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user), page: PageParams = Depends()
) -> Page[ProductOut]:
    products, total = await ListProducts(SqlProductRepository(db)).execute(user.id, page.limit, page.offset)
    return Page(items=[ProductOut(**p.__dict__) for p in products], total=total, limit=page.limit, offset=page.offset)


@router.post("/products/{product_id}/restock", response_model=None, status_code=204)
async def restock_product(product_id: str, body: RestockIn, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)) -> None:
    await RestockProduct(SqlInventoryRepository(db)).execute(product_id=product_id, quantity=body.quantity)
    await db.commit()
