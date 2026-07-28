import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()
_password_hasher = PasswordHasher()

TokenType = Literal["access", "refresh"]


@lru_cache
def _load_private_key() -> str:
    with open(settings.jwt_private_key_path) as f:
        return f.read()


@lru_cache
def _load_public_key() -> str:
    with open(settings.jwt_public_key_path) as f:
        return f.read()


def create_token(*, user_id: str, role: str, token_type: TokenType, jti: str | None = None) -> tuple[str, str]:
    """Returns (token, jti). jti lets the caller correlate a refresh token to its `refresh_tokens` row."""
    jti = jti or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    if token_type == "access":
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)
    else:
        expires_delta = timedelta(days=settings.refresh_token_expire_days)

    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": now + expires_delta,
    }
    token = jwt.encode(payload, _load_private_key(), algorithm=settings.jwt_algorithm)
    return token, jti


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _load_public_key(), algorithms=[settings.jwt_algorithm])


def hash_refresh_token(raw_token: str) -> str:
    """Refresh tokens are high-entropy (256-bit) already, so a fast SHA-256 digest
    is sufficient -- unlike OTP codes, there's no need for a slow KDF here."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def generate_otp_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(settings.otp_length))


def hash_otp_code(code: str, phone_number: str) -> str:
    return _password_hasher.hash(f"{settings.otp_pepper}:{phone_number}:{code}")


def verify_otp_code(code: str, phone_number: str, code_hash: str) -> bool:
    try:
        return _password_hasher.verify(code_hash, f"{settings.otp_pepper}:{phone_number}:{code}")
    except VerifyMismatchError:
        return False
