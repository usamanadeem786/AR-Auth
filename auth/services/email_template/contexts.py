from typing import Any

from pydantic import BaseModel, ConfigDict

from auth.db import AsyncSession
from auth.repositories import TenantRepository, UserRepository
from auth.schemas.tenant import Tenant
from auth.schemas.user import UserEmailContext
from auth.services.email_template.types import EmailTemplateType


class EmailContext(BaseModel):
    tenant: Tenant
    user: UserEmailContext | str
    model_config = ConfigDict(from_attributes=True)

    @classmethod
    async def create_sample_context(cls, session: AsyncSession):
        context_kwargs = await cls._get_sample_context_kwargs(session)
        return cls(**context_kwargs)

    @classmethod
    async def _get_sample_context_kwargs(cls, session: AsyncSession) -> dict[str, Any]:
        context_kwargs: dict[str, Any] = {}
        tenant_repository = TenantRepository(session)
        tenant = await tenant_repository.get_default()
        assert tenant is not None
        context_kwargs["tenant"] = tenant

        user_repository = UserRepository(session)
        user = await user_repository.get_one_by_tenant(tenant.id)
        if user is None:
            context_kwargs["user"] = UserEmailContext.create_sample(tenant)
        else:
            context_kwargs["user"] = user

        return context_kwargs


class WelcomeContext(EmailContext):
    pass


class VerifyEmailContext(EmailContext):
    code: str

    @classmethod
    async def _get_sample_context_kwargs(cls, session: AsyncSession) -> dict[str, Any]:
        context_kwargs = await super()._get_sample_context_kwargs(session)
        context_kwargs["code"] = "ABC123"
        return context_kwargs


class ForgotPasswordContext(EmailContext):
    reset_url: str

    @classmethod
    async def _get_sample_context_kwargs(cls, session: AsyncSession) -> dict[str, Any]:
        context_kwargs = await super()._get_sample_context_kwargs(session)
        context_kwargs["reset_url"] = "https://example.auth.dev/reset"
        return context_kwargs


class OrganizationInvitationContext(EmailContext):
    organization_name: str
    invitation_url: str

    @classmethod
    async def _get_sample_context_kwargs(cls, session: AsyncSession) -> dict[str, Any]:
        context_kwargs = await super()._get_sample_context_kwargs(session)
        context_kwargs["organization_name"] = "Example Organization"
        context_kwargs["invitation_url"] = "https://example.auth.dev/invitation"
        return context_kwargs


class SubscriptionGracePeriodContext(EmailContext):
    organization_name: str
    days_remaining: int
    payment_url: str
    subscription_name: str
    
    @classmethod
    async def _get_sample_context_kwargs(cls, session: AsyncSession) -> dict[str, Any]:
        context_kwargs = await super()._get_sample_context_kwargs(session)
        context_kwargs["organization_name"] = "Example Organization"
        context_kwargs["days_remaining"] = 5
        context_kwargs["payment_url"] = "https://example.auth.dev/billing"
        context_kwargs["subscription_name"] = "Pro Plan"
        return context_kwargs


class SubscriptionExpiredContext(EmailContext):
    organization_name: str
    payment_url: str
    subscription_name: str
    
    @classmethod
    async def _get_sample_context_kwargs(cls, session: AsyncSession) -> dict[str, Any]:
        context_kwargs = await super()._get_sample_context_kwargs(session)
        context_kwargs["organization_name"] = "Example Organization"
        context_kwargs["payment_url"] = "https://example.auth.dev/billing"
        context_kwargs["subscription_name"] = "Pro Plan"
        return context_kwargs


EMAIL_TEMPLATE_CONTEXT_CLASS_MAP: dict[EmailTemplateType, type[EmailContext]] = {
    EmailTemplateType.BASE: EmailContext,
    EmailTemplateType.WELCOME: WelcomeContext,
    EmailTemplateType.VERIFY_EMAIL: VerifyEmailContext,
    EmailTemplateType.FORGOT_PASSWORD: ForgotPasswordContext,
    EmailTemplateType.ORGANIZATION_INVITATION: OrganizationInvitationContext,
    EmailTemplateType.SUBSCRIPTION_GRACE_PERIOD: SubscriptionGracePeriodContext,
    EmailTemplateType.SUBSCRIPTION_EXPIRED: SubscriptionExpiredContext,
}
