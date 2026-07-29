"""Ledger sequence_no concurrency (platform-cross-cutting spec §3.3).

_AppendLedgerEntry reads the merchant's last sequence_no, then inserts
sequence_no + 1. Two simultaneous requests for the same merchant could
both read the same "last" row before either commits; the advisory lock
in acquire_merchant_lock serializes them so neither fails outright.
"""

import asyncio

from sqlalchemy import text

from app.core.db import AsyncSessionLocal


async def _register_and_login(client, sent_otps, phone: str, full_name: str = "Concurrency Merchant") -> tuple[str, str]:
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": full_name, "role": "MERCHANT"})
    body = r.json()
    return body["access_token"], body["user_id"]


async def test_concurrent_writes_for_the_same_merchant_both_succeed_with_sequential_sequence_numbers(client, sent_otps):
    token, _ = await _register_and_login(client, sent_otps, "+254799100001")
    headers = {"Authorization": f"Bearer {token}"}

    r1, r2 = await asyncio.gather(
        client.post("/ledger/transactions/expense", json={"amount": "10.00"}, headers=headers),
        client.post("/ledger/transactions/expense", json={"amount": "20.00"}, headers=headers),
    )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert sorted([r1.json()["sequence_no"], r2.json()["sequence_no"]]) == [1, 2]


async def test_different_merchants_are_not_serialized_by_the_advisory_lock(client, sent_otps):
    _, merchant_a_id = await _register_and_login(client, sent_otps, "+254799100002", "Merchant A")
    token_b, _ = await _register_and_login(client, sent_otps, "+254799100003", "Merchant B")

    hold_seconds = 1.5

    async def hold_merchant_a_lock() -> None:
        # Manually holds the same advisory lock RecordExpense would take for
        # merchant A, for long enough that merchant B's concurrent request
        # would visibly stall if the lock were (incorrectly) global rather
        # than keyed per-merchant.
        async with AsyncSessionLocal() as session, session.begin():
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:merchant_id))"), {"merchant_id": merchant_a_id})
            await asyncio.sleep(hold_seconds)

    async def request_for_merchant_b():
        loop = asyncio.get_event_loop()
        start = loop.time()
        r = await client.post("/ledger/transactions/expense", json={"amount": "5.00"}, headers={"Authorization": f"Bearer {token_b}"})
        return r, loop.time() - start

    _, (response_b, elapsed_b) = await asyncio.gather(hold_merchant_a_lock(), request_for_merchant_b())

    assert response_b.status_code == 200
    assert elapsed_b < hold_seconds
