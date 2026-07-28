from datetime import datetime
from typing import Any

from pydantic import BaseModel


class CreateUserIn(BaseModel):
    phone_number: str
    full_name: str
    role: str  # any of VALID_ROLES -- this is the only path that can set UNDERWRITER/ADMIN


class UpdateUserIn(BaseModel):
    full_name: str | None = None
    role: str | None = None


class UserOut(BaseModel):
    id: str
    phone_number: str
    full_name: str
    role: str
    created_at: datetime
    deleted_at: datetime | None
    created_by: str | None
    is_active: bool


class AuditLogEntryOut(BaseModel):
    id: str
    actor_user_id: str
    actor_full_name: str | None
    target_user_id: str | None
    target_full_name: str | None
    action: str
    detail: dict[str, Any] | None
    created_at: datetime
