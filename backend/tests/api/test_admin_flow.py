from app.modules.identity.infrastructure.repository import SqlUserRepository


async def _create_admin_and_login(client, sent_otps, db_session, phone: str, name: str = "Admin Test") -> str:
    # Admins can't come through the public signup flow -- create the row
    # directly (this is exactly what scripts/create_admin.py does), then log
    # in through the ordinary, unmodified OTP flow. No role is sent on
    # verify since the account already has one.
    await SqlUserRepository(db_session).create(phone_number=phone, full_name=name, role="ADMIN")
    await db_session.commit()

    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code})
    assert r.status_code == 200
    return r.json()["access_token"]


async def _register_merchant(client, sent_otps, phone: str) -> tuple[str, str]:
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": "Merchant X", "role": "MERCHANT"})
    body = r.json()
    return body["access_token"], body["user_id"]


async def test_underwriter_and_admin_cannot_self_register(client, sent_otps):
    for role in ("UNDERWRITER", "ADMIN"):
        phone = f"+25470000{1000 if role == 'UNDERWRITER' else 2000}"
        await client.post("/auth/otp/request", json={"phone_number": phone})
        code = sent_otps[phone]
        r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": "Sneaky", "role": role})
        assert r.status_code == 403


async def test_non_admin_cannot_access_admin_endpoints(client, sent_otps):
    token, _ = await _register_merchant(client, sent_otps, "+254760001111")
    r = await client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


async def test_admin_can_onboard_an_underwriter(client, sent_otps, db_session):
    admin_token = await _create_admin_and_login(client, sent_otps, db_session, "+254760002222")
    headers = {"Authorization": f"Bearer {admin_token}"}

    r = await client.post(
        "/admin/users",
        json={"phone_number": "+254760003333", "full_name": "New Underwriter", "role": "UNDERWRITER"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["role"] == "UNDERWRITER"

    # The newly-onboarded underwriter now just logs in normally -- no role
    # picker, since the account already has one.
    await client.post("/auth/otp/request", json={"phone_number": "+254760003333"})
    code = sent_otps["+254760003333"]
    login = await client.post("/auth/otp/verify", json={"phone_number": "+254760003333", "code": code})
    assert login.status_code == 200
    assert login.json()["role"] == "UNDERWRITER"


async def test_admin_cannot_onboard_duplicate_phone_number(client, sent_otps, db_session):
    admin_token = await _create_admin_and_login(client, sent_otps, db_session, "+254760004444")
    headers = {"Authorization": f"Bearer {admin_token}"}
    await _register_merchant(client, sent_otps, "+254760005555")

    r = await client.post("/admin/users", json={"phone_number": "+254760005555", "full_name": "Dup", "role": "UNDERWRITER"}, headers=headers)
    assert r.status_code == 409


async def test_admin_can_list_update_and_deactivate_users(client, sent_otps, db_session):
    admin_token = await _create_admin_and_login(client, sent_otps, db_session, "+254760006666")
    headers = {"Authorization": f"Bearer {admin_token}"}
    _, merchant_user_id = await _register_merchant(client, sent_otps, "+254760007777")

    listing = await client.get("/admin/users", params={"role": "MERCHANT"}, headers=headers)
    assert listing.status_code == 200
    assert any(u["id"] == merchant_user_id for u in listing.json()["items"])

    updated = await client.patch(f"/admin/users/{merchant_user_id}", json={"full_name": "Renamed Merchant"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Renamed Merchant"

    deactivate = await client.post(f"/admin/users/{merchant_user_id}/deactivate", headers=headers)
    assert deactivate.status_code == 204

    # Deactivated user must not be treated as brand-new on their next login attempt.
    await client.post("/auth/otp/request", json={"phone_number": "+254760007777"})
    code = sent_otps["+254760007777"]
    blocked_login = await client.post("/auth/otp/verify", json={"phone_number": "+254760007777", "code": code, "full_name": "x", "role": "MERCHANT"})
    assert blocked_login.status_code == 403

    reactivate = await client.post(f"/admin/users/{merchant_user_id}/reactivate", headers=headers)
    assert reactivate.status_code == 204

    await client.post("/auth/otp/request", json={"phone_number": "+254760007777"})
    code2 = sent_otps["+254760007777"]
    restored_login = await client.post("/auth/otp/verify", json={"phone_number": "+254760007777", "code": code2})
    assert restored_login.status_code == 200


async def test_deactivating_a_user_revokes_their_refresh_token(client, sent_otps, db_session):
    admin_token = await _create_admin_and_login(client, sent_otps, db_session, "+254760008888")
    headers = {"Authorization": f"Bearer {admin_token}"}

    await client.post("/auth/otp/request", json={"phone_number": "+254760009999"})
    code = sent_otps["+254760009999"]
    login = await client.post("/auth/otp/verify", json={"phone_number": "+254760009999", "code": code, "full_name": "Y", "role": "MERCHANT"})
    merchant_refresh = login.json()["refresh_token"]
    merchant_user_id = login.json()["user_id"]

    await client.post(f"/admin/users/{merchant_user_id}/deactivate", headers=headers)

    refresh_attempt = await client.post("/auth/refresh", json={"refresh_token": merchant_refresh})
    assert refresh_attempt.status_code == 401
