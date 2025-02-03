from datetime import UTC, datetime

from sqlalchemy import select

from auth.models import AuthorizationCode
from auth.repositories.base import BaseRepository, ExpiresAtMixin, UUIDRepositoryMixin


class AuthorizationCodeRepository(
    BaseRepository[AuthorizationCode],
    UUIDRepositoryMixin[AuthorizationCode],
    ExpiresAtMixin[AuthorizationCode],
):
    model = AuthorizationCode

    async def get_valid_by_code(self, code: str) -> AuthorizationCode | None:
        statement = select(AuthorizationCode).where(
            AuthorizationCode.code == code,
            AuthorizationCode.expires_at > datetime.now(UTC),
        )
        return await self.get_one_or_none(statement)

    async def get_by_code(self, code: str) -> AuthorizationCode | None:
        statement = select(AuthorizationCode).where(AuthorizationCode.code == code)
        return await self.get_one_or_none(statement)
