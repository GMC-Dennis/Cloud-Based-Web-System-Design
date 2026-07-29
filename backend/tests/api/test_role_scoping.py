"""Cross-cutting role-scoping (platform-cross-cutting spec §3.1).

Ledger/chama endpoints previously only checked "some valid login" via
get_current_user, not role -- an UNDERWRITER or ADMIN account could call
POST /ledger/transactions/sale directly even though the frontend nav never
shows them the option (nav-only scoping is not a security boundary). This
file asserts the router-level require_role(...) gates actually reject
out-of-role callers, for every write endpoint on both routers.
"""

import pytest

from app.modules.identity.infrastructure.repository import SqlUserRepository

LEDGER_WRITE_ENDPOINTS = [
    ("POST", "/ledger/transactions/sale", {"amount": "10", "line_items": []}),
    ("POST", "/ledger/transactions/expense", {"amount": "10"}),
    ("POST", "/ledger/transactions/supplier-payment", {"amount": "10"}),
    ("POST", "/ledger/products", {"name": "x", "unit_cost": "1", "unit_price": "2"}),
]

CHAMA_WRITE_ENDPOINTS = [
    ("POST", "/chama/groups", {"group_name": "x", "contribution_cycle": "MONTHLY", "cycle_amount": "1000"}),
]


async def _provision_and_login(client, sent_otps, db_session, phone: str, role: str, full_name: str) -> str:
    await SqlUserRepository(db_session).create(phone_number=phone, full_name=full_name, role=role)
    await db_session.commit()
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code})
    return r.json()["access_token"]


@pytest.mark.parametrize("method,path,body", LEDGER_WRITE_ENDPOINTS)
async def test_underwriter_cannot_write_to_ledger(client, sent_otps, db_session, method, path, body):
    token = await _provision_and_login(client, sent_otps, db_session, "+254755000001", "UNDERWRITER", "Blocked Underwriter")
    r = await client.request(method, path, json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.parametrize("method,path,body", LEDGER_WRITE_ENDPOINTS)
async def test_admin_cannot_write_to_ledger(client, sent_otps, db_session, method, path, body):
    token = await _provision_and_login(client, sent_otps, db_session, "+254755000002", "ADMIN", "Blocked Admin")
    r = await client.request(method, path, json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


async def test_chama_member_cannot_write_to_ledger(client, sent_otps):
    await client.post("/auth/otp/request", json={"phone_number": "+254755000003"})
    code = sent_otps["+254755000003"]
    verify = await client.post(
        "/auth/otp/verify",
        json={"phone_number": "+254755000003", "code": code, "full_name": "Chama Only", "role": "CHAMA_MEMBER"},
    )
    token = verify.json()["access_token"]

    r = await client.post("/ledger/products", json={"name": "x", "unit_cost": "1", "unit_price": "2"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


async def test_underwriter_cannot_read_ledger(client, sent_otps, db_session):
    token = await _provision_and_login(client, sent_otps, db_session, "+254755000004", "UNDERWRITER", "Blocked Reader")
    r = await client.get("/ledger/transactions", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.parametrize("method,path,body", CHAMA_WRITE_ENDPOINTS)
async def test_underwriter_cannot_write_to_chama(client, sent_otps, db_session, method, path, body):
    token = await _provision_and_login(client, sent_otps, db_session, "+254755000005", "UNDERWRITER", "Blocked Underwriter Two")
    r = await client.request(method, path, json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.parametrize("method,path,body", CHAMA_WRITE_ENDPOINTS)
async def test_admin_cannot_write_to_chama(client, sent_otps, db_session, method, path, body):
    token = await _provision_and_login(client, sent_otps, db_session, "+254755000006", "ADMIN", "Blocked Admin Two")
    r = await client.request(method, path, json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


async def test_underwriter_cannot_read_chama(client, sent_otps, db_session):
    token = await _provision_and_login(client, sent_otps, db_session, "+254755000007", "UNDERWRITER", "Blocked Chama Reader")
    r = await client.get("/chama/groups", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
