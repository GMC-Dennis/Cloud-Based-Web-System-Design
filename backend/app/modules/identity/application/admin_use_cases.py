from app.modules.identity.domain.entities import VALID_ROLES, User
from app.modules.identity.domain.repository import RefreshTokenRepository, UserRepository


class UserAlreadyExists(Exception):
    pass


class InvalidRole(Exception):
    pass


class UserNotFound(Exception):
    pass


class CreateUserByAdmin:
    """The only way an UNDERWRITER or ADMIN account gets created -- the
    public OTP signup flow (VerifyOtp) refuses those roles. The created
    account logs in afterward through the normal, unmodified OTP flow: since
    the phone number already exists with its role set, no role picker is
    ever shown to them."""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def execute(self, *, phone_number: str, full_name: str, role: str, created_by_admin_id: str) -> User:
        if role not in VALID_ROLES:
            raise InvalidRole(f"'{role}' is not a valid role")
        existing = await self.user_repo.get_by_phone_any_status(phone_number)
        if existing is not None:
            raise UserAlreadyExists(f"{phone_number} is already registered")
        return await self.user_repo.create(phone_number=phone_number, full_name=full_name, role=role, created_by=created_by_admin_id)


class ListUsers:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def execute(
        self, *, limit: int, offset: int, role: str | None = None, include_inactive: bool = False
    ) -> tuple[list[User], int]:
        return await self.user_repo.list_all(limit=limit, offset=offset, role=role, include_inactive=include_inactive)


class UpdateUser:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def execute(self, user_id: str, *, full_name: str | None = None, role: str | None = None) -> User:
        if role is not None and role not in VALID_ROLES:
            raise InvalidRole(f"'{role}' is not a valid role")
        target = await self.user_repo.get_by_id_any_status(user_id)
        if target is None:
            raise UserNotFound(user_id)
        return await self.user_repo.update(user_id, full_name=full_name, role=role)


class DeactivateUser:
    def __init__(self, user_repo: UserRepository, refresh_repo: RefreshTokenRepository):
        self.user_repo = user_repo
        self.refresh_repo = refresh_repo

    async def execute(self, user_id: str) -> None:
        target = await self.user_repo.get_by_id_any_status(user_id)
        if target is None:
            raise UserNotFound(user_id)
        await self.user_repo.deactivate(user_id)
        # Kills their ability to mint new access tokens immediately, rather
        # than leaving already-issued refresh tokens usable until they
        # happen to be noticed elsewhere.
        await self.refresh_repo.revoke_all_for_user(user_id)


class ReactivateUser:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def execute(self, user_id: str) -> None:
        target = await self.user_repo.get_by_id_any_status(user_id)
        if target is None:
            raise UserNotFound(user_id)
        await self.user_repo.reactivate(user_id)
