from datetime import datetime

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
