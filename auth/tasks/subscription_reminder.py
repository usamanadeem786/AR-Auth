from datetime import UTC, datetime

import dramatiq

from auth import schemas
from auth.models.organization_subscription import SubscriptionStatus
from auth.models.tenant import Tenant
from auth.models.user import User
from auth.repositories.organization_subscription import \
    OrganizationSubscriptionRepository
from auth.schemas.user import UserEmailContext
from auth.services.email_template.contexts import (
    SubscriptionExpiredContext, SubscriptionGracePeriodContext)
from auth.services.email_template.types import EmailTemplateType
from auth.tasks.base import TaskBase


class SubscriptionReminderTask(TaskBase):
    __name__ = "subscription_reminder"

    async def run(self):
        """
        Check for organization subscriptions in grace period or expired,
        and send appropriate email notifications.
        """
        now = datetime.now(UTC)

        # Process subscriptions in grace period
        await self._process_grace_period_subscriptions(now)

        # Process expired subscriptions
        await self._process_expired_subscriptions(now)

    async def _process_grace_period_subscriptions(self, now):
        """Send reminders for subscriptions in grace period"""
        async with self.get_main_session() as session:
            # Create repository
            repository = OrganizationSubscriptionRepository(session)

            # Get all expired subscriptions (some may be in grace period, some may not)
            subscriptions = await repository.get_expired_in_grace_period(now)

            for subscription in subscriptions:
                # Check if still in grace period
                if subscription.grace_expires_at > now:
                    organization = subscription.organization
                    user = organization.user
                    tenant = subscription.tier.subscription.tenant

                    # Calculate days remaining in grace period
                    days_remaining = subscription.days_until_grace_period_ends

                    # Only send reminder if there are days remaining
                    if days_remaining > 0:
                        await self._send_grace_period_email(
                            tenant,
                            user,
                            organization.name,
                            organization.id,
                            days_remaining,
                            subscription.tier.name,
                        )

    async def _send_grace_period_email(
        self,
        tenant: Tenant,
        user: User,
        organization_name: str,
        organization_id: str,
        days_remaining: int,
        subscription_name: str,
    ):
        """Send grace period email notification"""
        # Create context for email
        context = SubscriptionGracePeriodContext(
            tenant=schemas.tenant.Tenant.model_validate(tenant),
            user=schemas.user.UserEmailContext.model_validate(user),
            organization_name=organization_name,
            days_remaining=days_remaining,
            payment_url=f"{tenant.application_url}/billing?organization_id={organization_id}",
            subscription_name=subscription_name,
        )

        # Render email
        async with self._get_email_subject_renderer() as email_subject_renderer:
            subject = await email_subject_renderer.render(
                EmailTemplateType.SUBSCRIPTION_GRACE_PERIOD, context
            )

        async with self._get_email_template_renderer() as email_template_renderer:
            html = await email_template_renderer.render(
                EmailTemplateType.SUBSCRIPTION_GRACE_PERIOD, context
            )

        # Send email to organization owner
        self.email_provider.send_email(
            sender=tenant.get_email_sender(),
            recipient=(user.email, None),
            subject=subject,
            html=html,
        )

    async def _process_expired_subscriptions(self, now):
        """Process subscriptions that have passed grace period"""
        async with self.get_main_session() as session:
            # Create repository
            repository = OrganizationSubscriptionRepository(session)

            # Get all expired subscriptions
            subscriptions = await repository.get_expired_grace_ended(now)

            for subscription in subscriptions:
                # Check if grace period has ended
                if subscription.grace_expires_at <= now:
                    organization = subscription.organization
                    user = subscription.organization.user
                    tenant = subscription.tier.subscription.tenant

                    # Update subscription status to PAST_DUE using repository
                    subscription.status = SubscriptionStatus.PAST_DUE
                    await repository.update(subscription)

                    await self._send_expiration_email(
                        tenant,
                        user,
                        organization.name,
                        organization.id,
                        subscription.tier.name,
                    )

    async def _send_expiration_email(
        self,
        tenant: Tenant,
        user: User,
        organization_name: str,
        organization_id: str,
        subscription_name: str,
    ):
        """Send expiration email notification"""
        # Create context for email
        context = SubscriptionExpiredContext(
            tenant=schemas.tenant.Tenant.model_validate(tenant),
            user=schemas.user.UserEmailContext.model_validate(user),
            organization_name=organization_name,
            payment_url=f"{tenant.application_url}/billing?organization_id={organization_id}",
            subscription_name=subscription_name,
        )

        # Render email
        async with self._get_email_subject_renderer() as email_subject_renderer:
            subject = await email_subject_renderer.render(
                EmailTemplateType.SUBSCRIPTION_EXPIRED, context
            )

        async with self._get_email_template_renderer() as email_template_renderer:
            html = await email_template_renderer.render(
                EmailTemplateType.SUBSCRIPTION_EXPIRED, context
            )

        # Send email to organization owner
        self.email_provider.send_email(
            sender=tenant.get_email_sender(),
            recipient=(user.email, None),
            subject=subject,
            html=html,
        )


subscription_reminder = dramatiq.actor(SubscriptionReminderTask())
