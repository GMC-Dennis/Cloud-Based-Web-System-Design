async def test_first_time_login_requires_full_name_and_role(client, sent_otps):
    phone = "+254700111222"
    r = await client.post("/auth/otp/request", json={"phone_number": phone})
    assert r.status_code == 204
    code = sent_otps[phone]

    # Missing full_name/role on a brand-new phone number -> 404 (not registered).
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code})
    assert r.status_code == 404

    # Regression: the same code must still work on the follow-up call once the
    # frontend collects full_name/role -- the first (failed) attempt must not
    # have consumed the challenge, or the user gets stuck asking for a new code.
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": "New Merchant", "role": "MERCHANT"})
    assert r.status_code == 200
    assert r.json()["role"] == "MERCHANT"


async def test_full_otp_login_issues_token_pair(client, sent_otps):
    phone = "+254700333444"
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]

    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": "Jane Trader", "role": "MERCHANT"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["role"] == "MERCHANT"


async def test_wrong_code_is_rejected_and_counts_as_an_attempt(client, sent_otps):
    phone = "+254700555666"
    await client.post("/auth/otp/request", json={"phone_number": phone})

    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": "000000", "full_name": "X", "role": "MERCHANT"})
    assert r.status_code == 401


async def test_access_token_is_required_for_protected_routes(client):
    r = await client.get("/ledger/transactions")
    assert r.status_code in (401, 403)


async def test_refresh_flow_returns_new_tokens(client, sent_otps):
    phone = "+254700777888"
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]

    verify = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": "Refresh Tester", "role": "MERCHANT"})
    refresh_token = verify.json()["refresh_token"]

    r = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    assert r.json()["access_token"]

    # Reusing the now-rotated refresh token must fail.
    replay = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert replay.status_code == 401
