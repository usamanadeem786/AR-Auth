import uuid

import dramatiq

from auth import schemas
from auth.services.email_template.contexts import OrganizationInvitationContext
from auth.services.email_template.types import EmailTemplateType
from auth.tasks.base import TaskBase


class OnAfterOrganizationInvitationTask(TaskBase):
    __name__ = "on_after_organization_invitation"

    async def run(
        self,
        email: str,
        tenant_id: str,
        organization_name: str,
        invitation_url: str,
    ):
        tenant = await self._get_tenant(tenant_id)

        context = OrganizationInvitationContext(
            tenant=schemas.tenant.Tenant.model_validate(tenant),
            user=email,
            organization_name=organization_name,
            invitation_url=invitation_url,
        )

        async with self._get_email_subject_renderer() as email_subject_renderer:
            subject = await email_subject_renderer.render(
                EmailTemplateType.ORGANIZATION_INVITATION, context
            )

        async with self._get_email_template_renderer() as email_template_renderer:
            html = await email_template_renderer.render(
                EmailTemplateType.ORGANIZATION_INVITATION, context
            )

        self.email_provider.send_email(
            sender=tenant.get_email_sender(),
            recipient=(email, None),
            subject=subject,
            html=html,
        )


on_after_organization_invitation = dramatiq.actor(OnAfterOrganizationInvitationTask())
