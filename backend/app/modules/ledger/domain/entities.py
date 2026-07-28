from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class DukaTransaction:
    id: str
    merchant_id: str
    sequence_no: int
    amount: Decimal
    currency: str
    transaction_type: str
    is_credit: bool
    customer_phone: str | None
    previous_hash: str
    record_hash: str
    created_at: datetime


@dataclass
class Product:
    id: str
    merchant_id: str
    name: str
    unit_cost: Decimal
    unit_price: Decimal
    quantity_on_hand: int
    reorder_threshold: int | None
    updated_at: datetime


@dataclass
class InventoryMovement:
    id: str
    product_id: str
    duka_transaction_id: str | None
    quantity_delta: int
    created_at: datetime
