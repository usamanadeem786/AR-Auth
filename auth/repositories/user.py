from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from auth.models import User
from auth.repositories.base import BaseRepository, UUIDRepositoryMixin


class UserRepository(BaseRepository[User], UUIDRepositoryMixin[User]):
    model = User

    async def list_by_ids(self, ids: list[UUID4]) -> list[User]:
        statement = select(User).where(User.id.in_(ids))
        return await self.list(statement)

    async def get_by_id_and_tenant(self, id: UUID4, tenant: UUID4) -> User | None:
        statement = select(User).where(User.id == id, User.tenant_id == tenant)
        return await self.get_one_or_none(statement)

    async def get_by_email_and_tenant(self, email: str, tenant: UUID4) -> User | None:
        statement = select(User).where(
            User.email_lower == email.lower(), User.tenant_id == tenant
        )
        return await self.get_one_or_none(statement)

    async def get_by_email(self, email: str) -> User | None:
        statement = (
            select(User).where(User.email == email).options(joinedload(User.tenant))
        )
        return await self.get_one_or_none(statement)

    async def get_one_by_tenant(self, tenant: UUID4) -> User | None:
        statement = (
            select(User)
            .where(User.tenant_id == tenant)
            .order_by(User.created_at)
            .limit(1)
        )
        return await self.get_one_or_none(statement)

    async def count_all(self) -> int:
        statement = select(User)
        return await self._count(statement)

    async def count_by_tenant(self, tenant: UUID4) -> int:
        statement = select(User).where(User.tenant_id == tenant)
        return await self._count(statement)

    async def get_by_stripe_customer_id(self, stripe_customer_id: str) -> User | None:
        statement = select(User).where(User.stripe_customer_id == stripe_customer_id)
        return await self.get_one_or_none(statement)
