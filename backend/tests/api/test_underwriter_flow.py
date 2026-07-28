from app.modules.identity.infrastructure.repository import SqlUserRepository


async def _register_and_login(client, sent_otps, phone: str, role: str, full_name: str = "Test User") -> tuple[str, str]:
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": full_name, "role": role})
    body = r.json()
    return body["access_token"], body["user_id"]


async def _provision_underwriter_and_login(client, sent_otps, db_session, phone: str, full_name: str = "Underwriter") -> tuple[str, str]:
    user = await SqlUserRepository(db_session).create(phone_number=phone, full_name=full_name, role="UNDERWRITER")
    await db_session.commit()

    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code})
    return r.json()["access_token"], user.id


async def test_underwriter_can_search_borrowers_by_phone(client, sent_otps, db_session):
    underwriter_token, _ = await _provision_underwriter_and_login(client, sent_otps, db_session, "+254744000001")
    _, merchant_id = await _register_and_login(client, sent_otps, "+254744000002", "MERCHANT", "Findable Merchant")

    r = await client.get(
        "/underwriter/users/search", params={"phone": "744000002"}, headers={"Authorization": f"Bearer {underwriter_token}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == merchant_id
    assert body["items"][0]["full_name"] == "Findable Merchant"


async def test_borrower_search_excludes_admin_and_underwriter_accounts(client, sent_otps, db_session):
    underwriter_token, _ = await _provision_underwriter_and_login(client, sent_otps, db_session, "+254744000003")
    # Another underwriter that happens to share a phone-number substring should
    # never show up in a borrower search -- this endpoint finds borrowers,
    # not staff.
    await SqlUserRepository(db_session).create(phone_number="+254744000099", full_name="Other Underwriter", role="UNDERWRITER")
    await db_session.commit()

    r = await client.get(
        "/underwriter/users/search", params={"phone": "744000099"}, headers={"Authorization": f"Bearer {underwriter_token}"}
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0


async def test_borrower_search_excludes_deactivated_users(client, sent_otps, db_session):
    underwriter_token, _ = await _provision_underwriter_and_login(client, sent_otps, db_session, "+254744000004")
    _, merchant_id = await _register_and_login(client, sent_otps, "+254744000005", "MERCHANT", "Soon Deactivated")

    await SqlUserRepository(db_session).deactivate(merchant_id)
    await db_session.commit()

    r = await client.get(
        "/underwriter/users/search", params={"phone": "744000005"}, headers={"Authorization": f"Bearer {underwriter_token}"}
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0


async def test_non_underwriter_cannot_search_borrowers(client, sent_otps):
    token, _ = await _register_and_login(client, sent_otps, "+254744000007", "MERCHANT")
    r = await client.get("/underwriter/users/search", params={"phone": "744000007"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
