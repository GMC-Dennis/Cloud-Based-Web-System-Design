from app.core.audit_log import AuditLogEntry, AuditLogRepository
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

    def __init__(self, user_repo: UserRepository, audit_repo: AuditLogRepository):
        self.user_repo = user_repo
        self.audit_repo = audit_repo

    async def execute(self, *, phone_number: str, full_name: str, role: str, created_by_admin_id: str) -> User:
        if role not in VALID_ROLES:
            raise InvalidRole(f"'{role}' is not a valid role")
        existing = await self.user_repo.get_by_phone_any_status(phone_number)
        if existing is not None:
            raise UserAlreadyExists(f"{phone_number} is already registered")
        user = await self.user_repo.create(phone_number=phone_number, full_name=full_name, role=role, created_by=created_by_admin_id)
        await self.audit_repo.record(
            actor_user_id=created_by_admin_id,
            target_user_id=user.id,
            action="CREATE_USER",
            detail={"phone_number": phone_number, "full_name": full_name, "role": role},
        )
        return user


class ListUsers:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def execute(
        self, *, limit: int, offset: int, role: str | None = None, include_inactive: bool = False
    ) -> tuple[list[User], int]:
        return await self.user_repo.list_all(limit=limit, offset=offset, role=role, include_inactive=include_inactive)


class UpdateUser:
    """Role changes (including promotion straight to ADMIN) go through here
    with no additional gate beyond "caller is an admin" -- the ADMIN spec's
    open question about requiring a stricter path (e.g. a second admin's
    confirmation) is explicitly out of scope for this codebase (spec §5:
    "would need real product design"). What this use case does guarantee is
    that every change is attributable: the audit row below records exactly
    which fields changed and who changed them, so *if* a stricter policy
    gets built later there's already a complete history to reason from."""

    def __init__(self, user_repo: UserRepository, audit_repo: AuditLogRepository):
        self.user_repo = user_repo
        self.audit_repo = audit_repo

    async def execute(self, user_id: str, *, actor_id: str, full_name: str | None = None, role: str | None = None) -> User:
        if role is not None and role not in VALID_ROLES:
            raise InvalidRole(f"'{role}' is not a valid role")
        target = await self.user_repo.get_by_id_any_status(user_id)
        if target is None:
            raise UserNotFound(user_id)

        before: dict[str, str] = {}
        after: dict[str, str] = {}
        if full_name is not None and full_name != target.full_name:
            before["full_name"], after["full_name"] = target.full_name, full_name
        if role is not None and role != target.role:
            before["role"], after["role"] = target.role, role

        updated = await self.user_repo.update(user_id, full_name=full_name, role=role)
        await self.audit_repo.record(
            actor_user_id=actor_id, target_user_id=user_id, action="UPDATE_USER", detail={"before": before, "after": after}
        )
        return updated


class DeactivateUser:
    def __init__(self, user_repo: UserRepository, refresh_repo: RefreshTokenRepository, audit_repo: AuditLogRepository):
        self.user_repo = user_repo
        self.refresh_repo = refresh_repo
        self.audit_repo = audit_repo

    async def execute(self, user_id: str, *, actor_id: str) -> None:
        target = await self.user_repo.get_by_id_any_status(user_id)
        if target is None:
            raise UserNotFound(user_id)
        await self.user_repo.deactivate(user_id)
        # Kills their ability to mint new access tokens immediately, rather
        # than leaving already-issued refresh tokens usable until they
        # happen to be noticed elsewhere.
        await self.refresh_repo.revoke_all_for_user(user_id)
        await self.audit_repo.record(actor_user_id=actor_id, target_user_id=user_id, action="DEACTIVATE_USER")


class ReactivateUser:
    def __init__(self, user_repo: UserRepository, audit_repo: AuditLogRepository):
        self.user_repo = user_repo
        self.audit_repo = audit_repo

    async def execute(self, user_id: str, *, actor_id: str) -> None:
        target = await self.user_repo.get_by_id_any_status(user_id)
        if target is None:
            raise UserNotFound(user_id)
        await self.user_repo.reactivate(user_id)
        await self.audit_repo.record(actor_user_id=actor_id, target_user_id=user_id, action="REACTIVATE_USER")


class ListAuditLog:
    def __init__(self, audit_repo: AuditLogRepository, user_repo: UserRepository):
        self.audit_repo = audit_repo
        self.user_repo = user_repo

    async def execute(
        self,
        *,
        limit: int,
        offset: int,
        target_user_id: str | None = None,
        actor_user_id: str | None = None,
        action: str | None = None,
    ) -> tuple[list[AuditLogEntry], dict[str, str], int]:
        entries, total = await self.audit_repo.list_all(
            limit=limit, offset=offset, target_user_id=target_user_id, actor_user_id=actor_user_id, action=action
        )
        ids = {e.actor_user_id for e in entries} | {e.target_user_id for e in entries if e.target_user_id}
        names = await self.user_repo.get_full_names_by_ids(list(ids))
        return entries, names, total
