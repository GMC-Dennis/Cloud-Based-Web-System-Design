import pytest

from app.core.config import get_settings
from app.core.security import hash_refresh_token
from app.modules.identity.application.exceptions import RefreshTokenInvalid, RefreshTokenReused
from app.modules.identity.application.use_cases import RefreshTokenRotation
from app.modules.identity.infrastructure.repository import SqlRefreshTokenRepository, SqlUserRepository


async def test_rotation_issues_new_pair_and_revokes_old_token(db_session, test_user):
    from datetime import datetime, timedelta, timezone

    refresh_repo = SqlRefreshTokenRepository(db_session)
    raw_refresh = "original-refresh-token"
    token_id = await refresh_repo.create(user_id=test_user.id, token_hash=hash_refresh_token(raw_refresh), expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    await db_session.flush()

    use_case = RefreshTokenRotation(refresh_repo, SqlUserRepository(db_session), get_settings())
    new_access, new_refresh = await use_case.execute(raw_refresh)
    await db_session.flush()

    assert new_access and new_refresh
    old_row = await refresh_repo.get_by_hash(hash_refresh_token(raw_refresh))
    assert old_row["revoked_at"] is not None
    assert old_row["replaced_by"] is not None


async def test_reusing_a_rotated_token_revokes_the_whole_family(db_session, test_user):
    from datetime import datetime, timedelta, timezone

    refresh_repo = SqlRefreshTokenRepository(db_session)
    settings = get_settings()
    raw_refresh_1 = "session-token-v1"
    await refresh_repo.create(user_id=test_user.id, token_hash=hash_refresh_token(raw_refresh_1), expires_at=datetime.now(timezone.utc) + timedelta(days=30))
    await db_session.flush()

    use_case = RefreshTokenRotation(refresh_repo, SqlUserRepository(db_session), settings)
    # First rotation: legitimate.
    _, raw_refresh_2 = await use_case.execute(raw_refresh_1)
    await db_session.flush()

    # Second rotation using the *first* (already-rotated) token: this is the
    # replay/theft scenario -- must revoke the entire chain, not just deny this call.
    with pytest.raises(RefreshTokenReused):
        await use_case.execute(raw_refresh_1)
    await db_session.flush()

    # The legitimately-rotated second token must now be dead too.
    row_2 = await refresh_repo.get_by_hash(hash_refresh_token(raw_refresh_2))
    assert row_2["revoked_at"] is not None

    with pytest.raises(RefreshTokenInvalid):
        await use_case.execute(raw_refresh_2)


async def test_unknown_token_is_rejected(db_session, test_user):
    refresh_repo = SqlRefreshTokenRepository(db_session)
    use_case = RefreshTokenRotation(refresh_repo, SqlUserRepository(db_session), get_settings())
    with pytest.raises(RefreshTokenInvalid):
        await use_case.execute("never-issued-token")
