import pytest

from app.core.security import (
    create_token,
    decode_token,
    generate_otp_code,
    hash_otp_code,
    hash_refresh_token,
    verify_otp_code,
)


def test_access_token_roundtrip():
    token, jti = create_token(user_id="user-1", role="MERCHANT", token_type="access")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["role"] == "MERCHANT"
    assert payload["type"] == "access"
    assert payload["jti"] == jti


def test_refresh_token_has_longer_expiry_than_access_token():
    _, _ = create_token(user_id="user-1", role="MERCHANT", token_type="access")
    access = decode_token(create_token(user_id="user-1", role="MERCHANT", token_type="access")[0])
    refresh = decode_token(create_token(user_id="user-1", role="MERCHANT", token_type="refresh")[0])
    assert refresh["exp"] > access["exp"]


def test_otp_code_is_correct_length():
    from app.core.config import get_settings

    code = generate_otp_code()
    assert len(code) == get_settings().otp_length
    assert code.isdigit()


def test_otp_hash_verifies_correct_code():
    code = generate_otp_code()
    phone = "+254712345678"
    code_hash = hash_otp_code(code, phone)
    assert verify_otp_code(code, phone, code_hash)


def test_otp_hash_rejects_wrong_code():
    phone = "+254712345678"
    code_hash = hash_otp_code("123456", phone)
    assert not verify_otp_code("654321", phone, code_hash)


def test_otp_hash_is_phone_bound():
    # Same code, different phone number, must not verify -- the phone number
    # is mixed into the hashed payload precisely to prevent this.
    code = "123456"
    code_hash = hash_otp_code(code, "+254712345678")
    assert not verify_otp_code(code, "+254799999999", code_hash)


def test_refresh_token_hash_is_deterministic_and_one_way():
    raw = "some-high-entropy-refresh-token"
    assert hash_refresh_token(raw) == hash_refresh_token(raw)
    assert hash_refresh_token(raw) != raw
