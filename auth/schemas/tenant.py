from pydantic import UUID4, HttpUrl

from auth.schemas.generics import BaseModel, CreatedUpdatedAt, UUIDSchema
from auth.schemas.oauth_provider import OAuthProviderEmbedded
from auth.schemas.role import RoleEmbedded


class TenantCreate(BaseModel):
    name: str
    registration_allowed: bool = True
    theme_id: UUID4 | None = None
    logo_url: HttpUrl | None = None
    application_url: HttpUrl | None = None
    oauth_providers: list[UUID4] | None = None
    default_roles: list[UUID4] | None = None


class TenantUpdate(BaseModel):
    name: str | None = None
    registration_allowed: bool | None = None
    theme_id: UUID4 | None = None
    logo_url: HttpUrl | None = None
    application_url: HttpUrl | None = None
    oauth_providers: list[UUID4] | None = None
    default_roles: list[UUID4] | None = None


class BaseTenant(UUIDSchema, CreatedUpdatedAt):
    name: str
    default: bool
    slug: str
    registration_allowed: bool
    theme_id: UUID4 | None = None
    logo_url: HttpUrl | None = None
    application_url: HttpUrl | None = None


class Tenant(BaseTenant):
    oauth_providers: list[OAuthProviderEmbedded]
    default_roles: list[RoleEmbedded]


class TenantEmbedded(BaseTenant):
    pass


class TenantEmailContext(BaseTenant):
    pass
