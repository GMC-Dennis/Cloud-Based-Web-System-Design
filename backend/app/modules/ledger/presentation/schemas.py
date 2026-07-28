from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SaleLineItemIn(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class RecordSaleIn(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = "KES"
    is_credit: bool = False
    customer_phone: str | None = None
    line_items: list[SaleLineItemIn] = []


class RecordExpenseIn(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = "KES"


class RecordSupplierPaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = "KES"


class TransactionOut(BaseModel):
    id: str
    merchant_id: str
    sequence_no: int
    amount: Decimal
    currency: str
    transaction_type: str
    is_credit: bool
    customer_phone: str | None
    record_hash: str
    created_at: datetime


class CreateProductIn(BaseModel):
    name: str
    unit_cost: Decimal = Field(ge=0)
    unit_price: Decimal = Field(ge=0)
    reorder_threshold: int = 0


class RestockIn(BaseModel):
    quantity: int = Field(gt=0)


class ProductOut(BaseModel):
    id: str
    merchant_id: str
    name: str
    unit_cost: Decimal
    unit_price: Decimal
    quantity_on_hand: int
    reorder_threshold: int | None
    updated_at: datetime
