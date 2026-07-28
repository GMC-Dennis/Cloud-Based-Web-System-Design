from decimal import Decimal

from app.modules.scoring.infrastructure.repository import SqlCreditScoreRepository
from app.modules.identity.infrastructure.repository import SqlUserRepository


async def _register_and_login(client, sent_otps, phone: str, role: str, full_name: str = "Test User") -> tuple[str, str]:
    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code, "full_name": full_name, "role": role})
    body = r.json()
    return body["access_token"], body["user_id"]


async def _provision_underwriter_and_login(client, sent_otps, db_session, phone: str, full_name: str = "Underwriter") -> tuple[str, str]:
    # UNDERWRITER can no longer self-register (see test_admin_flow.py) --
    # provision the account directly, exactly as scripts/create_admin.py /
    # POST /admin/users would, then log in through the ordinary OTP flow.
    user = await SqlUserRepository(db_session).create(phone_number=phone, full_name=full_name, role="UNDERWRITER")
    await db_session.commit()

    await client.post("/auth/otp/request", json={"phone_number": phone})
    code = sent_otps[phone]
    r = await client.post("/auth/otp/verify", json={"phone_number": phone, "code": code})
    return r.json()["access_token"], user.id


async def test_underwriter_can_create_algorithmic_loan_without_knowing_borrower_id(client, sent_otps, db_session):
    # Regression test: the underwriter_applicant_view (TDD §4/§8.1) never
    # exposes a raw user_id, only credit_score_id -- so /loans must be able
    # to resolve the borrower from credit_score_id alone.
    _, merchant_user_id = await _register_and_login(client, sent_otps, "+254722000111", "MERCHANT")
    underwriter_token, _ = await _provision_underwriter_and_login(client, sent_otps, db_session, "+254722000222", "Uma Underwriter")

    score = await SqlCreditScoreRepository(db_session).save(
        user_id=merchant_user_id, credit_score=750, recommended_limit=Decimal("20000"), risk_tier="LOW", model_version="rf_v3_2026_06", shap_explanation={}
    )
    await db_session.commit()

    headers = {"Authorization": f"Bearer {underwriter_token}"}
    r = await client.post(
        "/loans",
        json={"credit_score_id": score.id, "underwriting_method": "ALGORITHMIC", "principal": "5000", "interest_rate": "0.05"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["borrower_id"] == merchant_user_id


async def test_loan_creation_without_borrower_id_or_credit_score_id_is_rejected(client, sent_otps, db_session):
    token, _ = await _provision_underwriter_and_login(client, sent_otps, db_session, "+254722000444", "Uma Three")

    r = await client.post(
        "/loans",
        json={"underwriting_method": "ALGORITHMIC", "principal": "5000", "interest_rate": "0.05"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422
