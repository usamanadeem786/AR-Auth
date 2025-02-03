from pydantic import UUID4

from auth.schemas.generics import BaseModel, CreatedUpdatedAt
from auth.schemas.role import RoleEmbedded


class UserRoleCreate(BaseModel):
    id: UUID4


class BaseUserRole(CreatedUpdatedAt):
    user_id: UUID4
    role_id: UUID4


class UserRole(BaseUserRole):
    role: RoleEmbedded
