import re
from dataclasses import dataclass
from datetime import datetime


class InvalidPhoneNumber(ValueError):
    pass


@dataclass(frozen=True)
class PhoneNumber:
    """E.164-ish value object. Kenyan numbers in particular, but not restricted to them."""

    value: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"\+?[1-9]\d{7,14}", self.value):
            raise InvalidPhoneNumber(f"'{self.value}' is not a valid phone number")

    def __str__(self) -> str:
        return self.value


VALID_ROLES = ("MERCHANT", "CHAMA_MEMBER", "UNDERWRITER", "ADMIN")
SELF_ASSIGNABLE_ROLES = ("MERCHANT", "CHAMA_MEMBER")


@dataclass
class User:
    id: str
    phone_number: str
    full_name: str
    role: str
    created_at: datetime
    deleted_at: datetime | None = None
    created_by: str | None = None

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None
