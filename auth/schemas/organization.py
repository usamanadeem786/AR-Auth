from datetime import datetime

from pydantic import UUID4, BaseModel, EmailStr

from auth.models.organization import OrganizationRole
from auth.schemas.generics import CreatedUpdatedAt, UUIDSchema


class BaseOrganization(BaseModel):
    name: str
    description: str | None = None


class OrganizationCreate(BaseOrganization):
    pass


class OrganizationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class OrganizationRead(UUIDSchema, CreatedUpdatedAt):
    name: str
    description: str | None = None


class Organization(UUIDSchema, CreatedUpdatedAt):
    name: str
    description: str | None = None


class BaseOrganizationMember(UUIDSchema, CreatedUpdatedAt):
    user_id: UUID4


class OrganizationMemberUpdate(BaseOrganizationMember):
    pass


class UserInfo(BaseModel):
    id: UUID4
    email: EmailStr

    class Config:
        from_attributes = True


class PermissionInfo(BaseModel):
    id: UUID4
    name: str

    class Config:
        from_attributes = True


class OrganizationMember(BaseOrganizationMember):
    organization_id: UUID4
    permissions: list[PermissionInfo] | None = None
    user: UserInfo
    role: OrganizationRole

    class Config:
        from_attributes = True


class OrganizationMemberPermissionCreate(BaseModel):
    permission_id: list[UUID4] | None = None


class BaseOrganizationInvitation(BaseModel):
    email: EmailStr
    role: OrganizationRole


class OrganizationInvitationRead(BaseOrganizationInvitation):
    permissions: list[PermissionInfo] | None = None

    class Config:
        from_attributes = True


class OrganizationInvitationCreate(BaseOrganizationInvitation):
    email: EmailStr
    role: OrganizationRole
    permissions: list[UUID4] | None = None


class OrganizationInvitationUpdate(BaseOrganizationInvitation):
    pass


class OrganizationInvitation(UUIDSchema, CreatedUpdatedAt, BaseOrganizationInvitation):
    expires_at: datetime
    is_expired: bool
