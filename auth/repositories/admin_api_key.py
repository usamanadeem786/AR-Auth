from sqlalchemy import select

from auth.models import AdminAPIKey
from auth.repositories.base import BaseRepository, UUIDRepositoryMixin


class AdminAPIKeyRepository(
    BaseRepository[AdminAPIKey], UUIDRepositoryMixin[AdminAPIKey]
):
    model = AdminAPIKey

    async def get_by_token(self, token: str) -> AdminAPIKey | None:
        statement = select(AdminAPIKey).where(AdminAPIKey.token == token)
        return await self.get_one_or_none(statement)
