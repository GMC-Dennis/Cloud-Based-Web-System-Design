from datetime import datetime, timezone
from decimal import Decimal

from app.modules.ledger.domain.hashing import GENESIS_HASH, compute_record_hash


def _hash(**overrides):
    base = dict(
        previous_hash=GENESIS_HASH,
        merchant_id="11111111-1111-1111-1111-111111111111",
        sequence_no=1,
        amount=Decimal("100.00"),
        currency="KES",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return compute_record_hash(**base)


def test_hash_is_deterministic():
    assert _hash() == _hash()


def test_hash_is_64_hex_chars():
    h = _hash()
    assert len(h) == 64
    int(h, 16)  # raises if not hex


def test_hash_changes_with_amount():
    assert _hash(amount=Decimal("100.00")) != _hash(amount=Decimal("100.01"))


def test_hash_changes_with_sequence_no():
    assert _hash(sequence_no=1) != _hash(sequence_no=2)


def test_hash_changes_with_previous_hash():
    assert _hash(previous_hash=GENESIS_HASH) != _hash(previous_hash="1" * 64)


def test_genesis_hash_is_64_zeros():
    assert GENESIS_HASH == "0" * 64
