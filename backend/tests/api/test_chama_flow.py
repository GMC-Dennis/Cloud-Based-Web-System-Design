async def _register_and_login(client, sent_otps, phone: str, full_name: str = "Chama User") -> tuple[str, str]:
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post(
        "/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": full_name, "role": "CHAMA_MEMBER"}
    )
    body = r.json()
    return body["access_token"], body["user_id"]


async def _create_chama_with_member(client, sent_otps):
    chair_token, chair_user_id = await _register_and_login(client, sent_otps, "+254733000001", "Chairperson")
    member_token, member_user_id = await _register_and_login(client, sent_otps, "+254733000002", "Plain Member")

    chair_headers = {"Authorization": f"Bearer {chair_token}"}
    group = (
        await client.post(
            "/chama/groups", json={"group_name": "Test Chama", "contribution_cycle": "MONTHLY", "cycle_amount": "1000"}, headers=chair_headers
        )
    ).json()
    chama_id = group["id"]

    added = (
        await client.post(f"/chama/groups/{chama_id}/members", json={"user_id": member_user_id}, headers=chair_headers)
    ).json()
    member_id = added["id"]

    members = (await client.get(f"/chama/groups/{chama_id}/members", headers=chair_headers)).json()
    chair_member_id = next(m["id"] for m in members["items"] if m["user_id"] == chair_user_id)

    return {
        "chama_id": chama_id,
        "chair_token": chair_token,
        "chair_headers": chair_headers,
        "chair_member_id": chair_member_id,
        "member_token": member_token,
        "member_headers": {"Authorization": f"Bearer {member_token}"},
        "member_id": member_id,
        "member_user_id": member_user_id,
    }


async def test_member_can_view_own_contribution_history(client, sent_otps):
    ctx = await _create_chama_with_member(client, sent_otps)

    record = await client.post(
        "/chama/contributions",
        json={"member_id": ctx["member_id"], "cycle_due_date": "2026-08-01", "amount_due": "1000", "amount_paid": "1000"},
        headers=ctx["chair_headers"],
    )
    assert record.status_code == 200

    r = await client.get(f"/chama/members/{ctx['member_id']}/contributions", headers=ctx["member_headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["cycle_due_date"] == "2026-08-01"
    assert body["items"][0]["is_on_time"] is True


async def test_officer_can_view_a_members_contribution_history(client, sent_otps):
    ctx = await _create_chama_with_member(client, sent_otps)
    await client.post(
        "/chama/contributions",
        json={"member_id": ctx["member_id"], "cycle_due_date": "2026-08-01", "amount_due": "1000", "amount_paid": "1000"},
        headers=ctx["chair_headers"],
    )

    r = await client.get(f"/chama/members/{ctx['member_id']}/contributions", headers=ctx["chair_headers"])
    assert r.status_code == 200
    assert r.json()["total"] == 1


async def test_non_member_cannot_view_contribution_history(client, sent_otps):
    ctx = await _create_chama_with_member(client, sent_otps)
    outsider_token, _ = await _register_and_login(client, sent_otps, "+254733000003", "Outsider")

    r = await client.get(
        f"/chama/members/{ctx['member_id']}/contributions", headers={"Authorization": f"Bearer {outsider_token}"}
    )
    assert r.status_code == 403


async def test_contribution_history_for_unknown_member_is_404(client, sent_otps):
    token, _ = await _register_and_login(client, sent_otps, "+254733000004", "Solo User")
    r = await client.get(
        "/chama/members/00000000-0000-0000-0000-000000000000/contributions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


async def test_member_can_view_payout_schedule(client, sent_otps):
    ctx = await _create_chama_with_member(client, sent_otps)

    scheduled = await client.post(
        f"/chama/payouts?chama_id={ctx['chama_id']}",
        json={"recipient_member_id": ctx["member_id"], "payout_amount": "5000", "scheduled_date": "2026-09-01"},
        headers=ctx["chair_headers"],
    )
    assert scheduled.status_code == 200

    r = await client.get(f"/chama/groups/{ctx['chama_id']}/payouts", headers=ctx["member_headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["recipient_member_id"] == ctx["member_id"]


async def test_non_member_cannot_view_payout_schedule(client, sent_otps):
    ctx = await _create_chama_with_member(client, sent_otps)
    outsider_token, _ = await _register_and_login(client, sent_otps, "+254733000006", "Outsider Two")

    r = await client.get(f"/chama/groups/{ctx['chama_id']}/payouts", headers={"Authorization": f"Bearer {outsider_token}"})
    assert r.status_code == 403


async def test_non_officer_cannot_schedule_a_payout(client, sent_otps):
    ctx = await _create_chama_with_member(client, sent_otps)

    r = await client.post(
        f"/chama/payouts?chama_id={ctx['chama_id']}",
        json={"recipient_member_id": ctx["member_id"], "payout_amount": "5000", "scheduled_date": "2026-09-01"},
        headers=ctx["member_headers"],
    )
    assert r.status_code == 403


async def test_officer_can_schedule_a_payout(client, sent_otps):
    ctx = await _create_chama_with_member(client, sent_otps)

    r = await client.post(
        f"/chama/payouts?chama_id={ctx['chama_id']}",
        json={"recipient_member_id": ctx["chair_member_id"], "payout_amount": "5000", "scheduled_date": "2026-09-01"},
        headers=ctx["chair_headers"],
    )
    assert r.status_code == 200
    assert r.json()["recipient_member_id"] == ctx["chair_member_id"]
