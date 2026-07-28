async def _register_and_login(client, sent_otps, phone: str) -> str:
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": "Idem Test", "role": "MERCHANT"})
    return r.json()["access_token"]


async def test_retry_with_same_idempotency_key_returns_original_response_no_duplicate(client, sent_otps):
    token = await _register_and_login(client, sent_otps, "+254733000111")
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "retry-key-1"}

    first = await client.post("/ledger/transactions/sale", json={"amount": "100.00"}, headers=headers)
    assert first.status_code == 200
    first_id = first.json()["id"]

    # Simulates a client retrying after a timeout, same key, same request.
    second = await client.post("/ledger/transactions/sale", json={"amount": "100.00"}, headers=headers)
    assert second.status_code == 200
    assert second.json()["id"] == first_id

    listing = await client.get("/ledger/transactions", headers={"Authorization": f"Bearer {token}"})
    assert listing.json()["total"] == 1  # only one real ledger row, despite two HTTP calls


async def test_different_idempotency_keys_create_separate_transactions(client, sent_otps):
    token = await _register_and_login(client, sent_otps, "+254733000222")
    auth_header = {"Authorization": f"Bearer {token}"}

    r1 = await client.post("/ledger/transactions/sale", json={"amount": "50.00"}, headers={**auth_header, "Idempotency-Key": "key-a"})
    r2 = await client.post("/ledger/transactions/sale", json={"amount": "50.00"}, headers={**auth_header, "Idempotency-Key": "key-b"})
    assert r1.json()["id"] != r2.json()["id"]

    listing = await client.get("/ledger/transactions", headers=auth_header)
    assert listing.json()["total"] == 2


async def test_no_idempotency_key_means_no_deduplication(client, sent_otps):
    token = await _register_and_login(client, sent_otps, "+254733000333")
    auth_header = {"Authorization": f"Bearer {token}"}

    r1 = await client.post("/ledger/transactions/sale", json={"amount": "75.00"}, headers=auth_header)
    r2 = await client.post("/ledger/transactions/sale", json={"amount": "75.00"}, headers=auth_header)
    assert r1.json()["id"] != r2.json()["id"]

    listing = await client.get("/ledger/transactions", headers=auth_header)
    assert listing.json()["total"] == 2
