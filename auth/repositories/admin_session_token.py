from sqlalchemy import select

from auth.models import AdminSessionToken
from auth.repositories.base import BaseRepository, UUIDRepositoryMixin


class AdminSessionTokenRepository(
    BaseRepository[AdminSessionToken], UUIDRepositoryMixin[AdminSessionToken]
):
    model = AdminSessionToken

    async def get_by_token(self, token: str) -> AdminSessionToken | None:
        statement = select(AdminSessionToken).where(AdminSessionToken.token == token)
        return await self.get_one_or_none(statement)
