from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import require_role
from app.core.pagination import Page, PageParams
from app.modules.identity.application.underwriter_use_cases import SearchBorrowers
from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.repository import SqlUserRepository
from app.modules.identity.presentation.underwriter_schemas import BorrowerSearchOut

router = APIRouter(prefix="/underwriter", tags=["underwriter"], dependencies=[Depends(require_role("UNDERWRITER"))])


def _to_out(user: User) -> BorrowerSearchOut:
    return BorrowerSearchOut(id=user.id, full_name=user.full_name, phone_number=user.phone_number, role=user.role)


@router.get("/users/search", response_model=Page[BorrowerSearchOut])
async def search_borrowers(phone: str, db: AsyncSession = Depends(get_db), page: PageParams = Depends()) -> Page[BorrowerSearchOut]:
    users, total = await SearchBorrowers(SqlUserRepository(db)).execute(phone_query=phone, limit=page.limit, offset=page.offset)
    return Page(items=[_to_out(u) for u in users], total=total, limit=page.limit, offset=page.offset)
