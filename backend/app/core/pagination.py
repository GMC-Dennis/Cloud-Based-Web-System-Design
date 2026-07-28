"""Shared limit/offset pagination (TDD v1.3).

Added ahead of real merchant volume per the TDD's own §7.1 capacity-planning
section -- an unpaginated `GET /ledger/transactions` is fine for a demo
merchant with a dozen rows and a real problem for one with a year of daily
sales. Kept to simple limit/offset rather than cursor-based pagination:
sufficient for a pilot's data volumes, and every affected list already has a
`created_at`/similar index to make the offset scan cheap at this scale.
"""

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams:
    def __init__(
        self,
        limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
        offset: int = Query(default=0, ge=0),
    ):
        self.limit = limit
        self.offset = offset
