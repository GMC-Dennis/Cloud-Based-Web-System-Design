async def _register_and_login(client, sent_otps, phone: str) -> str:
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": "Merchant Test", "role": "MERCHANT"})
    return r.json()["access_token"]


async def test_recording_sales_builds_the_hash_chain(client, sent_otps):
    # Requires Redis reachable at settings.redis_url (RecordSale invalidates
    # the score cache on every write) -- run via `docker compose exec backend pytest`.
    token = await _register_and_login(client, sent_otps, "+254711000111")
    headers = {"Authorization": f"Bearer {token}"}

    r1 = await client.post("/ledger/transactions/sale", json={"amount": "150.00"}, headers=headers)
    assert r1.status_code == 200
    assert r1.json()["sequence_no"] == 1

    r2 = await client.post("/ledger/transactions/expense", json={"amount": "20.00"}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["sequence_no"] == 2  # shared per-merchant sequence across transaction types

    listing = await client.get("/ledger/transactions", headers=headers)
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


async def test_product_and_restock_flow(client, sent_otps):
    token = await _register_and_login(client, sent_otps, "+254711222333")
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post("/ledger/products", json={"name": "Cooking Oil 1L", "unit_cost": "180", "unit_price": "220"}, headers=headers)
    assert create.status_code == 200
    product_id = create.json()["id"]
    assert create.json()["quantity_on_hand"] == 0

    restock = await client.post(f"/ledger/products/{product_id}/restock", json={"quantity": 24}, headers=headers)
    assert restock.status_code == 204

    products = await client.get("/ledger/products", headers=headers)
    body = products.json()
    assert body["total"] == 1
    assert body["items"][0]["quantity_on_hand"] == 24
