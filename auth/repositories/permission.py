from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.sql import Select

from auth.models import Permission, UserPermission
from auth.repositories.base import BaseRepository, UUIDRepositoryMixin


class PermissionRepository(BaseRepository[Permission], UUIDRepositoryMixin[Permission]):
    model = Permission

    async def get_by_codename(self, codename: str) -> Permission | None:
        statement = select(Permission).where(Permission.codename == codename)
        return await self.get_one_or_none(statement)

    def get_user_permissions_statement(self, user: UUID4) -> Select:
        statement = (
            select(Permission)
            .join(UserPermission, UserPermission.permission_id == Permission.id)
            .where(UserPermission.user_id == user)
        )

        return statement

    async def get_by_ids(self, ids: list[UUID4]) -> list[Permission]:
        statement = select(Permission).where(Permission.id.in_(ids))
        return await self.list(statement)
