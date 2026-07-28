import hashlib
from datetime import datetime
from decimal import Decimal

GENESIS_HASH = "0" * 64


def compute_record_hash(
    *, previous_hash: str, merchant_id: str, sequence_no: int, amount: Decimal, currency: str, created_at: datetime
) -> str:
    """Must stay internally consistent, not match any particular external format --
    the `trg_validate_ledger_chain` DB trigger only checks that this row's
    previous_hash equals the prior row's record_hash, it never recomputes
    record_hash itself. What matters is every writer uses this same function."""
    payload = "|".join(
        [previous_hash, merchant_id, str(sequence_no), f"{amount:.2f}", currency, created_at.isoformat()]
    )
    return hashlib.sha256(payload.encode()).hexdigest()
