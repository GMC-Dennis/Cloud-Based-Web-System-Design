from app.modules.identity.domain.entities import User
from app.modules.identity.domain.repository import UserRepository


class SearchBorrowers:
    """Underwriter-scoped borrower lookup for manual/override loan creation
    (UNDERWRITER spec §4.2). Deliberately narrower than admin's user
    management endpoint: read-only, MERCHANT/CHAMA_MEMBER only, never
    surfaces ADMIN/UNDERWRITER accounts -- this finds a borrower, it isn't
    a general user directory."""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def execute(self, *, phone_query: str, limit: int, offset: int) -> tuple[list[User], int]:
        return await self.user_repo.search_borrowers_by_phone(phone_query, limit, offset)
