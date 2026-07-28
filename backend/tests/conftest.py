import os
from pathlib import Path

# Must run before any `app.*` import: app.core.db builds its engine at import
# time from DATABASE_URL, and app.core.security lazily loads JWT keys from
# these paths. Point both at a test DB / disposable keypair before anything
# else in the app package gets imported (conftest.py always loads first).
BACKEND_ROOT = Path(__file__).resolve().parent.parent
TEST_KEYS_DIR = BACKEND_ROOT / "tests" / ".keys"

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://fintech_admin:change_me_locally@localhost:5434/fintech_ledger"),
)
os.environ.setdefault("JWT_PRIVATE_KEY_PATH", str(TEST_KEYS_DIR / "jwt_private.pem"))
os.environ.setdefault("JWT_PUBLIC_KEY_PATH", str(TEST_KEYS_DIR / "jwt_public.pem"))
os.environ.setdefault("OTP_PEPPER", "test-pepper")


def _ensure_test_jwt_keys() -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    priv_path = Path(os.environ["JWT_PRIVATE_KEY_PATH"])
    pub_path = Path(os.environ["JWT_PUBLIC_KEY_PATH"])
    if priv_path.exists() and pub_path.exists():
        return
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pub_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )


_ensure_test_jwt_keys()

import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import text


@pytest.fixture(scope="session")
def event_loop():
    """One event loop for the whole test session.

    app.core.db.engine is a module-level singleton, created once at import
    time and bound to whatever event loop is running at that moment. pytest-
    asyncio's default gives every test function its own loop, so the second
    test to touch that shared engine gets a pooled connection tied to a now-
    dead loop ("got Future attached to a different loop"). Pinning one loop
    for the session keeps it valid for every fixture and test.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


TABLES_IN_TRUNCATE_ORDER = (
    "idempotency_keys, loan_repayments, loans, credit_scores, "
    "chama_payouts, chama_contributions, chama_members, chama_groups, "
    "inventory_movements, products, duka_transactions, "
    "otp_challenges, refresh_tokens, users"
)


@pytest.fixture(scope="session")
def apply_migrations():
    """Run Alembic against the test DB once per session. Only pulled in by
    `db_session` -- pure unit tests (hashing, security) don't need a DB at
    all and shouldn't be gated on Postgres being reachable.

    Deliberately does NOT downgrade afterward: DATABASE_URL here is whatever
    the environment points at, and in local dev (docker-compose.dev.yml)
    that's the same database the app itself uses -- there's no separate test
    DB provisioned yet. A downgrade-to-base teardown would drop the app's
    schema out from under it the moment `pytest` finishes. Per-test isolation
    already comes from truncating tables in `db_session`, not from a fresh
    schema each run, so skipping the downgrade costs nothing.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest_asyncio.fixture
async def db_session(apply_migrations):
    from app.core.db import AsyncSessionLocal, engine

    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {TABLES_IN_TRUNCATE_ORDER} RESTART IDENTITY CASCADE"))

    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_user(db_session):
    from app.modules.identity.infrastructure.repository import SqlUserRepository

    user = await SqlUserRepository(db_session).create(phone_number="+254712345678", full_name="Test Merchant", role="MERCHANT")
    await db_session.commit()
    return user
