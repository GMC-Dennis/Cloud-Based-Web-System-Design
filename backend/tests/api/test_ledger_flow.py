async def _register_and_login(client, sent_otps, phone: str, full_name: str = "Merchant Test") -> tuple[str, str]:
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": full_name, "role": "MERCHANT"})
    body = r.json()
    return body["access_token"], body["user_id"]


async def _create_product(client, headers, name: str = "Cooking Oil 1L") -> str:
    r = await client.post("/ledger/products", json={"name": name, "unit_cost": "180", "unit_price": "220"}, headers=headers)
    return r.json()["id"]


async def test_recording_sales_builds_the_hash_chain(client, sent_otps):
    # Requires Redis reachable at settings.redis_url (RecordSale invalidates
    # the score cache on every write) -- run via `docker compose exec backend pytest`.
    token, _ = await _register_and_login(client, sent_otps, "+254711000111")
    headers = {"Authorization": f"Bearer {token}"}
    product_id = await _create_product(client, headers)
    await client.post(f"/ledger/products/{product_id}/restock", json={"quantity": 10}, headers=headers)

    r1 = await client.post(
        "/ledger/transactions/sale", json={"amount": "150.00", "line_items": [{"product_id": product_id, "quantity": 1}]}, headers=headers
    )
    assert r1.status_code == 200
    assert r1.json()["sequence_no"] == 1  # creating the product and restocking don't touch duka_transactions

    r2 = await client.post("/ledger/transactions/expense", json={"amount": "20.00"}, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["sequence_no"] == 2  # shared per-merchant sequence across transaction types

    listing = await client.get("/ledger/transactions", headers=headers)
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


async def test_sale_without_line_items_is_rejected(client, sent_otps):
    # Regression test for the anti-gaming fix: a sale with no line items is
    # unverifiable revenue with no corresponding inventory movement.
    token, _ = await _register_and_login(client, sent_otps, "+254711000222")
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.post("/ledger/transactions/sale", json={"amount": "150.00"}, headers=headers)
    assert r.status_code == 422


async def test_sale_cannot_reference_another_merchants_product(client, sent_otps):
    # Regression test: a merchant must not be able to record a sale against
    # -- and thereby decrement -- another merchant's inventory.
    owner_token, _ = await _register_and_login(client, sent_otps, "+254711000333", "Product Owner")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    product_id = await _create_product(client, owner_headers)
    await client.post(f"/ledger/products/{product_id}/restock", json={"quantity": 10}, headers=owner_headers)

    attacker_token, _ = await _register_and_login(client, sent_otps, "+254711000444", "Attacker")
    attacker_headers = {"Authorization": f"Bearer {attacker_token}"}

    r = await client.post(
        "/ledger/transactions/sale",
        json={"amount": "999.00", "line_items": [{"product_id": product_id, "quantity": 1}]},
        headers=attacker_headers,
    )
    assert r.status_code == 403


async def test_product_and_restock_flow(client, sent_otps):
    token, _ = await _register_and_login(client, sent_otps, "+254711222333")
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


async def test_cannot_restock_another_merchants_product(client, sent_otps):
    owner_token, _ = await _register_and_login(client, sent_otps, "+254711000555", "Owner Two")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    product_id = await _create_product(client, owner_headers)

    attacker_token, _ = await _register_and_login(client, sent_otps, "+254711000666", "Attacker Two")
    attacker_headers = {"Authorization": f"Bearer {attacker_token}"}

    r = await client.post(f"/ledger/products/{product_id}/restock", json={"quantity": 100}, headers=attacker_headers)
    assert r.status_code == 403
