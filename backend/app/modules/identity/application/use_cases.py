from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.core.security import (
    create_token,
    generate_otp_code,
    hash_otp_code,
    hash_refresh_token,
    verify_otp_code,
)
from app.modules.identity.application.exceptions import (
    AccountDeactivated,
    OtpInvalid,
    OtpLocked,
    OtpRateLimited,
    RefreshTokenInvalid,
    RefreshTokenReused,
    RoleNotSelfAssignable,
    UserNotRegistered,
)
from app.modules.identity.domain.entities import SELF_ASSIGNABLE_ROLES, PhoneNumber, User
from app.modules.identity.domain.repository import (
    OtpChallengeRepository,
    RefreshTokenRepository,
    UserRepository,
)
from app.modules.identity.infrastructure.otp_sender import OtpSender


class RequestOtp:
    def __init__(self, otp_repo: OtpChallengeRepository, sender: OtpSender, settings: Settings):
        self.otp_repo = otp_repo
        self.sender = sender
        self.settings = settings

    async def execute(self, phone_number: str) -> None:
        phone = str(PhoneNumber(phone_number))
        window_start = datetime.now(timezone.utc) - timedelta(minutes=self.settings.otp_request_window_minutes)
        recent = await self.otp_repo.count_recent_requests(phone, since=window_start)
        if recent >= self.settings.otp_max_requests_per_window:
            raise OtpRateLimited(f"Too many OTP requests for {phone}, try again later")

        code = generate_otp_code()
        code_hash = hash_otp_code(code, phone)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.settings.otp_expire_minutes)
        await self.otp_repo.create(
            phone_number=phone, code_hash=code_hash, max_attempts=self.settings.otp_max_attempts, expires_at=expires_at
        )
        await self.sender.send(phone, code)


class VerifyOtp:
    def __init__(self, otp_repo: OtpChallengeRepository, user_repo: UserRepository, refresh_repo: RefreshTokenRepository, settings: Settings):
        self.otp_repo = otp_repo
        self.user_repo = user_repo
        self.refresh_repo = refresh_repo
        self.settings = settings

    async def execute(
        self, phone_number: str, code: str, *, full_name: str | None = None, role: str | None = None
    ) -> tuple[str, str, User]:
        phone = str(PhoneNumber(phone_number))
        challenge = await self.otp_repo.get_active(phone)
        if challenge is None:
            raise OtpInvalid("No active OTP challenge for this phone number")
        if challenge["attempt_count"] >= challenge["max_attempts"]:
            raise OtpLocked("Too many failed attempts, request a new code")

        if not verify_otp_code(code, phone, challenge["code_hash"]):
            await self.otp_repo.increment_attempt(challenge["id"])
            raise OtpInvalid("Incorrect code")

        # Checked before the active-only lookup: a deactivated phone number
        # must not be silently treated as brand-new (which would let it
        # re-register with a fresh name/role and defeat the deactivation).
        existing_any_status = await self.user_repo.get_by_phone_any_status(phone)
        if existing_any_status is not None and not existing_any_status.is_active:
            raise AccountDeactivated("This account has been deactivated")

        # Deliberately checked before consuming the challenge: a brand-new
        # phone number's first verify call (no full_name/role yet) needs to
        # raise UserNotRegistered while leaving the code valid, so the
        # follow-up call from the frontend's registration step can reuse the
        # same code instead of the user being asked to enter a fresh one.
        user = await self.user_repo.get_by_phone(phone)
        if user is None:
            if full_name is None or role is None:
                raise UserNotRegistered("First-time login requires full_name and role")
            if role not in SELF_ASSIGNABLE_ROLES:
                # UNDERWRITER/ADMIN must be provisioned by an existing admin
                # (see admin_use_cases.CreateUserByAdmin) -- self-assigning
                # into them here would be a privilege-escalation gap.
                raise RoleNotSelfAssignable(f"Role '{role}' cannot be self-assigned at signup")
            user = await self.user_repo.create(phone_number=phone, full_name=full_name, role=role)

        await self.otp_repo.mark_consumed(challenge["id"])

        access_token, _ = create_token(user_id=user.id, role=user.role, token_type="access")
        refresh_token, _ = create_token(user_id=user.id, role=user.role, token_type="refresh")
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.settings.refresh_token_expire_days)
        await self.refresh_repo.create(user_id=user.id, token_hash=hash_refresh_token(refresh_token), expires_at=expires_at)

        return access_token, refresh_token, user


class RefreshTokenRotation:
    def __init__(self, refresh_repo: RefreshTokenRepository, user_repo: UserRepository, settings: Settings):
        self.refresh_repo = refresh_repo
        self.user_repo = user_repo
        self.settings = settings

    async def execute(self, raw_refresh_token: str) -> tuple[str, str]:
        token_hash = hash_refresh_token(raw_refresh_token)
        row = await self.refresh_repo.get_by_hash(token_hash)
        if row is None:
            raise RefreshTokenInvalid("Unknown refresh token")

        if row["replaced_by"] is not None:
            # This token was already rotated once -- being presented again means
            # it was stolen/replayed. Revoke the whole session, force re-auth.
            await self.refresh_repo.revoke_family(row["id"])
            raise RefreshTokenReused("Refresh token reuse detected, session revoked")

        if row["revoked_at"] is not None:
            raise RefreshTokenInvalid("Refresh token revoked")

        if row["expires_at"] < datetime.now(timezone.utc):
            raise RefreshTokenInvalid("Refresh token expired")

        user = await self.user_repo.get_by_id(row["user_id"])
        if user is None:
            raise RefreshTokenInvalid("User no longer active")

        new_access, _ = create_token(user_id=user.id, role=user.role, token_type="access")
        new_refresh, _ = create_token(user_id=user.id, role=user.role, token_type="refresh")
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.settings.refresh_token_expire_days)
        new_id = await self.refresh_repo.create(user_id=user.id, token_hash=hash_refresh_token(new_refresh), expires_at=expires_at)
        await self.refresh_repo.mark_replaced(row["id"], new_id)

        return new_access, new_refresh


class Logout:
    def __init__(self, refresh_repo: RefreshTokenRepository):
        self.refresh_repo = refresh_repo

    async def execute(self, raw_refresh_token: str) -> None:
        token_hash = hash_refresh_token(raw_refresh_token)
        row = await self.refresh_repo.get_by_hash(token_hash)
        if row is not None:
            await self.refresh_repo.revoke(row["id"])
