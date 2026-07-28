from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit_log import AuditLogEntry, AuditLogRepository
from app.core.db import get_db
from app.core.deps import CurrentUser, get_current_user, require_role
from app.core.pagination import Page, PageParams
from app.modules.identity.application.admin_use_cases import (
    CreateUserByAdmin,
    DeactivateUser,
    InvalidRole,
    ListAuditLog,
    ListUsers,
    ReactivateUser,
    UpdateUser,
    UserAlreadyExists,
    UserNotFound,
)
from app.modules.identity.domain.entities import InvalidPhoneNumber, User
from app.modules.identity.infrastructure.repository import SqlRefreshTokenRepository, SqlUserRepository
from app.modules.identity.presentation.admin_schemas import AuditLogEntryOut, CreateUserIn, UpdateUserIn, UserOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role("ADMIN"))])


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, phone_number=user.phone_number, full_name=user.full_name, role=user.role,
        created_at=user.created_at, deleted_at=user.deleted_at, created_by=user.created_by, is_active=user.is_active,
    )


def _audit_to_out(entry: AuditLogEntry, names: dict[str, str]) -> AuditLogEntryOut:
    return AuditLogEntryOut(
        id=entry.id,
        actor_user_id=entry.actor_user_id,
        actor_full_name=names.get(entry.actor_user_id),
        target_user_id=entry.target_user_id,
        target_full_name=names.get(entry.target_user_id) if entry.target_user_id else None,
        action=entry.action,
        detail=entry.detail,
        created_at=entry.created_at,
    )


@router.post("/users", response_model=UserOut)
async def create_user(body: CreateUserIn, db: AsyncSession = Depends(get_db), admin: CurrentUser = Depends(get_current_user)) -> UserOut:
    try:
        user = await CreateUserByAdmin(SqlUserRepository(db), AuditLogRepository(db)).execute(
            phone_number=body.phone_number, full_name=body.full_name, role=body.role, created_by_admin_id=admin.id
        )
    except InvalidPhoneNumber as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except InvalidRole as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except UserAlreadyExists as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    return _to_out(user)


@router.get("/users", response_model=Page[UserOut])
async def list_users(
    role: str | None = None,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    page: PageParams = Depends(),
) -> Page[UserOut]:
    users, total = await ListUsers(SqlUserRepository(db)).execute(
        limit=page.limit, offset=page.offset, role=role, include_inactive=include_inactive
    )
    return Page(items=[_to_out(u) for u in users], total=total, limit=page.limit, offset=page.offset)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str, body: UpdateUserIn, db: AsyncSession = Depends(get_db), admin: CurrentUser = Depends(get_current_user)
) -> UserOut:
    try:
        user = await UpdateUser(SqlUserRepository(db), AuditLogRepository(db)).execute(
            user_id, actor_id=admin.id, full_name=body.full_name, role=body.role
        )
    except InvalidRole as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except UserNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    await db.commit()
    return _to_out(user)


@router.post("/users/{user_id}/deactivate", response_model=None, status_code=204)
async def deactivate_user(user_id: str, db: AsyncSession = Depends(get_db), admin: CurrentUser = Depends(get_current_user)) -> None:
    try:
        await DeactivateUser(SqlUserRepository(db), SqlRefreshTokenRepository(db), AuditLogRepository(db)).execute(
            user_id, actor_id=admin.id
        )
    except UserNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    await db.commit()


@router.post("/users/{user_id}/reactivate", response_model=None, status_code=204)
async def reactivate_user(user_id: str, db: AsyncSession = Depends(get_db), admin: CurrentUser = Depends(get_current_user)) -> None:
    try:
        await ReactivateUser(SqlUserRepository(db), AuditLogRepository(db)).execute(user_id, actor_id=admin.id)
    except UserNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    await db.commit()


@router.get("/audit-log", response_model=Page[AuditLogEntryOut])
async def list_audit_log(
    target_user_id: str | None = None,
    actor_user_id: str | None = None,
    action: str | None = None,
    db: AsyncSession = Depends(get_db),
    page: PageParams = Depends(),
) -> Page[AuditLogEntryOut]:
    entries, names, total = await ListAuditLog(AuditLogRepository(db), SqlUserRepository(db)).execute(
        limit=page.limit, offset=page.offset, target_user_id=target_user_id, actor_user_id=actor_user_id, action=action
    )
    return Page(items=[_audit_to_out(e, names) for e in entries], total=total, limit=page.limit, offset=page.offset)
