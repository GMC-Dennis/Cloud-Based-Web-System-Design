import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.domain.entities import User
from app.modules.identity.infrastructure.models import OtpChallenge, RefreshToken
from app.modules.identity.infrastructure.models import User as UserModel


def _to_domain_user(row: UserModel) -> User:
    return User(
        id=str(row.id),
        phone_number=row.phone_number,
        full_name=row.full_name,
        role=row.role,
        created_at=row.created_at,
        deleted_at=row.deleted_at,
        created_by=str(row.created_by) if row.created_by else None,
    )


class SqlUserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_phone(self, phone_number: str) -> User | None:
        row = (
            await self.session.execute(
                select(UserModel).where(UserModel.phone_number == phone_number, UserModel.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        return _to_domain_user(row) if row else None

    async def get_by_phone_any_status(self, phone_number: str) -> User | None:
        row = (
            await self.session.execute(select(UserModel).where(UserModel.phone_number == phone_number))
        ).scalar_one_or_none()
        return _to_domain_user(row) if row else None

    async def get_by_id(self, user_id: str) -> User | None:
        row = await self.session.get(UserModel, uuid.UUID(user_id))
        return _to_domain_user(row) if row and row.deleted_at is None else None

    async def get_by_id_any_status(self, user_id: str) -> User | None:
        row = await self.session.get(UserModel, uuid.UUID(user_id))
        return _to_domain_user(row) if row else None

    async def create(self, *, phone_number: str, full_name: str, role: str, created_by: str | None = None) -> User:
        row = UserModel(
            phone_number=phone_number, full_name=full_name, role=role, created_by=uuid.UUID(created_by) if created_by else None
        )
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _to_domain_user(row)

    async def list_all(
        self, *, limit: int, offset: int, role: str | None = None, include_inactive: bool = False
    ) -> tuple[list[User], int]:
        conditions = []
        if role is not None:
            conditions.append(UserModel.role == role)
        if not include_inactive:
            conditions.append(UserModel.deleted_at.is_(None))

        total = (await self.session.execute(select(func.count()).select_from(UserModel).where(*conditions))).scalar_one()
        rows = (
            await self.session.execute(
                select(UserModel).where(*conditions).order_by(UserModel.created_at.desc(), UserModel.id).limit(limit).offset(offset)
            )
        ).scalars()
        return [_to_domain_user(r) for r in rows], total

    async def update(self, user_id: str, *, full_name: str | None = None, role: str | None = None) -> User:
        row = await self.session.get(UserModel, uuid.UUID(user_id))
        if full_name is not None:
            row.full_name = full_name
        if role is not None:
            row.role = role
        await self.session.flush()
        await self.session.refresh(row)
        return _to_domain_user(row)

    async def deactivate(self, user_id: str) -> None:
        await self.session.execute(
            update(UserModel).where(UserModel.id == uuid.UUID(user_id)).values(deleted_at=datetime.now(timezone.utc))
        )

    async def reactivate(self, user_id: str) -> None:
        await self.session.execute(update(UserModel).where(UserModel.id == uuid.UUID(user_id)).values(deleted_at=None))

    async def get_full_names_by_ids(self, user_ids: list[str]) -> dict[str, str]:
        if not user_ids:
            return {}
        rows = await self.session.execute(
            select(UserModel.id, UserModel.full_name).where(UserModel.id.in_(uuid.UUID(u) for u in user_ids))
        )
        return {str(row.id): row.full_name for row in rows}

    async def search_borrowers_by_phone(self, phone_query: str, limit: int, offset: int) -> tuple[list[User], int]:
        conditions = (
            UserModel.deleted_at.is_(None),
            UserModel.role.in_(("MERCHANT", "CHAMA_MEMBER")),
            UserModel.phone_number.ilike(f"%{phone_query}%"),
        )
        total = (await self.session.execute(select(func.count()).select_from(UserModel).where(*conditions))).scalar_one()
        rows = (
            await self.session.execute(
                select(UserModel).where(*conditions).order_by(UserModel.full_name, UserModel.id).limit(limit).offset(offset)
            )
        ).scalars()
        return [_to_domain_user(r) for r in rows], total


class SqlOtpChallengeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def count_recent_requests(self, phone_number: str, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(OtpChallenge)
            .where(OtpChallenge.phone_number == phone_number, OtpChallenge.created_at >= since)
        )
        return result.scalar_one()

    async def create(self, *, phone_number: str, code_hash: str, max_attempts: int, expires_at: datetime) -> str:
        row = OtpChallenge(
            phone_number=phone_number, code_hash=code_hash, max_attempts=max_attempts, expires_at=expires_at
        )
        self.session.add(row)
        await self.session.flush()
        return str(row.id)

    async def get_active(self, phone_number: str) -> dict | None:
        row = (
            await self.session.execute(
                select(OtpChallenge)
                .where(
                    OtpChallenge.phone_number == phone_number,
                    OtpChallenge.consumed_at.is_(None),
                    OtpChallenge.expires_at > datetime.now(timezone.utc),
                )
                .order_by(OtpChallenge.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "code_hash": row.code_hash,
            "attempt_count": row.attempt_count,
            "max_attempts": row.max_attempts,
        }

    async def increment_attempt(self, challenge_id: str) -> None:
        await self.session.execute(
            update(OtpChallenge)
            .where(OtpChallenge.id == uuid.UUID(challenge_id))
            .values(attempt_count=OtpChallenge.attempt_count + 1)
        )

    async def mark_consumed(self, challenge_id: str) -> None:
        await self.session.execute(
            update(OtpChallenge)
            .where(OtpChallenge.id == uuid.UUID(challenge_id))
            .values(consumed_at=datetime.now(timezone.utc))
        )


class SqlRefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, *, user_id: str, token_hash: str, expires_at: datetime) -> str:
        row = RefreshToken(user_id=uuid.UUID(user_id), token_hash=token_hash, expires_at=expires_at)
        self.session.add(row)
        await self.session.flush()
        return str(row.id)

    async def get_by_hash(self, token_hash: str) -> dict | None:
        row = (
            await self.session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        ).scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "user_id": str(row.user_id),
            "replaced_by": str(row.replaced_by) if row.replaced_by else None,
            "expires_at": row.expires_at,
            "revoked_at": row.revoked_at,
        }

    async def mark_replaced(self, token_id: str, replaced_by: str) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.id == uuid.UUID(token_id))
            .values(replaced_by=uuid.UUID(replaced_by), revoked_at=datetime.now(timezone.utc))
        )

    async def revoke(self, token_id: str) -> None:
        await self.session.execute(
            update(RefreshToken).where(RefreshToken.id == uuid.UUID(token_id)).values(revoked_at=datetime.now(timezone.utc))
        )

    async def revoke_all_for_user(self, user_id: str) -> None:
        """Called when deactivating an account -- an already-issued refresh
        token must stop being able to mint new access tokens immediately,
        not just wait for the user row's deleted_at to be noticed elsewhere."""
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == uuid.UUID(user_id), RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )

    async def revoke_family(self, token_id: str) -> None:
        # Walk backward to the root of the rotation chain, then forward,
        # collecting every token that's ever been part of this session.
        family_ids: set[uuid.UUID] = {uuid.UUID(token_id)}

        current = await self.session.get(RefreshToken, uuid.UUID(token_id))
        while current is not None:
            parent = (
                await self.session.execute(select(RefreshToken).where(RefreshToken.replaced_by == current.id))
            ).scalar_one_or_none()
            if parent is None or parent.id in family_ids:
                break
            family_ids.add(parent.id)
            current = parent

        current = await self.session.get(RefreshToken, uuid.UUID(token_id))
        while current is not None and current.replaced_by is not None and current.replaced_by not in family_ids:
            family_ids.add(current.replaced_by)
            current = await self.session.get(RefreshToken, current.replaced_by)

        if family_ids:
            await self.session.execute(
                update(RefreshToken).where(RefreshToken.id.in_(family_ids)).values(revoked_at=datetime.now(timezone.utc))
            )
