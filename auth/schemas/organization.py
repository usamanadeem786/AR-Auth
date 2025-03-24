from datetime import datetime
from typing import Optional

from pydantic import UUID4, BaseModel, EmailStr, Field, HttpUrl, computed_field

from auth.models.organization import OrganizationRole
from auth.models.organization_subscription import SubscriptionStatus
from auth.models.subscription import SubscriptionInterval
from auth.schemas.generics import CreatedUpdatedAt, UUIDSchema
from auth.schemas.subscription import TierInfoRead


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
    client_id: str = Field(..., min_length=32, max_length=255)
    redirect_uri: HttpUrl | None = None


class OrganizationInvitationUpdate(BaseOrganizationInvitation):
    pass


class OrganizationInvitation(UUIDSchema, CreatedUpdatedAt, BaseOrganizationInvitation):
    expires_at: datetime
    is_expired: bool


class OrganizationSubscriptionRead(UUIDSchema):
    accounts: int
    expires_at: datetime
    grace_period: int
    quantity: int
    interval: SubscriptionInterval | None
    interval_count: int | None
    status: SubscriptionStatus

    # Calculated properties
    is_active: bool
    is_in_grace_period: bool
    days_until_expiry: int
    days_until_grace_period_ends: int

    tier: Optional[TierInfoRead] = None

    class Config:
        from_attributes = True


class OrganizationSubscriptionCalculated(BaseModel):
    expires_at: datetime | None = None
    grace_period: int | None = None

    status: SubscriptionStatus

    # Calculated properties
    is_active: bool
    is_in_grace_period: bool
    days_until_expiry: int
    days_until_grace_period_ends: int

    class Config:
        from_attributes = True


class RolePermission(BaseModel):
    name: str
    permissions: list[PermissionInfo] = []

    class Config:
        from_attributes = True
