async def _register_and_login(client, sent_otps, phone: str) -> str:
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": "Page Test", "role": "MERCHANT"})
    return r.json()["access_token"]


async def _create_and_stock_product(client, headers, quantity: int = 100) -> str:
    create = await client.post("/ledger/products", json={"name": "Test Product", "unit_cost": "10", "unit_price": "20"}, headers=headers)
    product_id = create.json()["id"]
    await client.post(f"/ledger/products/{product_id}/restock", json={"quantity": quantity}, headers=headers)
    return product_id


async def test_transaction_list_pagination_slices_correctly(client, sent_otps):
    token = await _register_and_login(client, sent_otps, "+254744000111")
    headers = {"Authorization": f"Bearer {token}"}
    product_id = await _create_and_stock_product(client, headers)

    for i in range(5):
        r = await client.post(
            "/ledger/transactions/sale",
            json={"amount": f"{10 + i}.00", "line_items": [{"product_id": product_id, "quantity": 1}]},
            headers=headers,
        )
        assert r.status_code == 200

    page1 = (await client.get("/ledger/transactions", params={"limit": 2, "offset": 0}, headers=headers)).json()
    assert page1["total"] == 5
    assert page1["limit"] == 2
    assert page1["offset"] == 0
    assert len(page1["items"]) == 2

    page2 = (await client.get("/ledger/transactions", params={"limit": 2, "offset": 2}, headers=headers)).json()
    assert len(page2["items"]) == 2
    assert {t["id"] for t in page1["items"]}.isdisjoint({t["id"] for t in page2["items"]})

    last_page = (await client.get("/ledger/transactions", params={"limit": 2, "offset": 4}, headers=headers)).json()
    assert len(last_page["items"]) == 1


async def test_pagination_limit_is_capped(client, sent_otps):
    token = await _register_and_login(client, sent_otps, "+254744000222")
    headers = {"Authorization": f"Bearer {token}"}

    r = await client.get("/ledger/transactions", params={"limit": 9999}, headers=headers)
    assert r.status_code == 422  # exceeds MAX_LIMIT


async def test_pagination_defaults_when_no_params_given(client, sent_otps):
    token = await _register_and_login(client, sent_otps, "+254744000333")
    headers = {"Authorization": f"Bearer {token}"}
    product_id = await _create_and_stock_product(client, headers)
    await client.post(
        "/ledger/transactions/sale", json={"amount": "10.00", "line_items": [{"product_id": product_id, "quantity": 1}]}, headers=headers
    )

    r = await client.get("/ledger/transactions", headers=headers)
    body = r.json()
    assert body["limit"] == 50
    assert body["offset"] == 0
