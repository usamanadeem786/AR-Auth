from datetime import UTC, datetime, timedelta

from pydantic import UUID4
from sqlalchemy import and_, func, select
from sqlalchemy.orm import joinedload

from auth.models.organization import Organization
from auth.models.organization_subscription import (OrganizationSubscription,
                                                   SubscriptionStatus)
from auth.models.permission import Permission
from auth.models.role import Role
from auth.models.subscription import (Subscription, SubscriptionTier,
                                      SubscriptionTierMode)
from auth.repositories.base import BaseRepository, UUIDRepositoryMixin


class OrganizationSubscriptionRepository(
    BaseRepository[OrganizationSubscription],
    UUIDRepositoryMixin[OrganizationSubscription],
):
    model = OrganizationSubscription

    async def get_by_organization_and_tier(
        self, organization_id: UUID4, tier_id: UUID4
    ) -> OrganizationSubscription | None:
        statement = select(self.model).where(
            OrganizationSubscription.organization_id == organization_id,
            OrganizationSubscription.tier_id == tier_id,
        )
        return await self.list(statement)

    async def get_active_by_organization(
        self, organization_id: UUID4
    ) -> list[OrganizationSubscription]:
        now = datetime.now(UTC)
        statement = (
            select(self.model)
            .where(
                OrganizationSubscription.organization_id == organization_id,
                OrganizationSubscription.status == SubscriptionStatus.ACTIVE,
                OrganizationSubscription.expires_at
                + timedelta(days=OrganizationSubscription.grace_period)
                > now,
            )
            .options(
                joinedload(OrganizationSubscription.tier),
            )
        )
        return await self.list(statement)

    async def get_all_by_organization(
        self, organization_id: UUID4
    ) -> list[OrganizationSubscription]:
        statement = (
            select(self.model)
            .where(
                OrganizationSubscription.organization_id == organization_id,
            )
            .options(
                joinedload(OrganizationSubscription.tier).joinedload(
                    SubscriptionTier.subscription
                ),
            )
        )
        return await self.list(statement)

    async def get_all_active(self) -> list[OrganizationSubscription]:
        statement = select(self.model).where(
            OrganizationSubscription.status == SubscriptionStatus.ACTIVE,
        )
        return await self.list(statement)

    async def get_by_stripe_subscription_id(
        self, stripe_subscription_id: str
    ) -> OrganizationSubscription | None:
        statement = select(self.model).where(
            OrganizationSubscription.stripe_subscription_id == stripe_subscription_id
        )
        return await self.get_one_or_none(statement)

    async def get_by_user(self, user_id: UUID4) -> list[OrganizationSubscription]:
        statement = (
            select(self.model)
            .where(self.model.organization.has(Organization.user_id == user_id))
            .options(
                joinedload(OrganizationSubscription.tier).joinedload(
                    SubscriptionTier.subscription
                ),
            )
        )
        return await self.list(statement)

    async def get_by_organization_and_user(
        self, organization_id: UUID4, user_id: UUID4
    ) -> list[OrganizationSubscription]:
        statement = (
            select(self.model)
            .where(
                self.model.organization_id == organization_id,
                self.model.organization.has(Organization.user_id == user_id),
            )
            .options(
                joinedload(OrganizationSubscription.tier).joinedload(
                    SubscriptionTier.subscription
                ),
            )
        )
        return await self.list(statement)

    async def get_organization_accounts(self, organization_id: UUID4) -> int:
        statement = select(func.sum(self.model.accounts).label("total_accounts")).where(
            OrganizationSubscription.organization_id == organization_id,
        )
        result = await self.session.execute(statement)
        total = result.scalar()
        return total or 0

    async def get_expired_in_grace_period(
        self, now: datetime
    ) -> list[OrganizationSubscription]:
        """Get subscriptions that have expired but are still in grace period"""
        statement = (
            select(self.model)
            .where(
                and_(
                    OrganizationSubscription.expires_at < now,
                    OrganizationSubscription.status == SubscriptionStatus.ACTIVE,
                    OrganizationSubscription.tier.has(
                        mode=SubscriptionTierMode.RECURRING
                    ),
                )
            )
            .options(
                joinedload(OrganizationSubscription.organization).joinedload(
                    Organization.user
                ),
                joinedload(OrganizationSubscription.tier)
                .joinedload(SubscriptionTier.subscription)
                .joinedload(Subscription.tenant),
            )
        )
        return await self.list(statement)

    async def get_expired_grace_ended(
        self, now: datetime
    ) -> list[OrganizationSubscription]:
        """Get subscriptions that have expired and grace period has ended"""
        # Using the same query as get_expired_in_grace_period, but filtering will be done
        # in the caller based on grace_expires_at
        return await self.get_expired_in_grace_period(now)

    async def get_by_organization_with_roles_permissions(
        self, organization_id: UUID4
    ) -> list[OrganizationSubscription]:
        """Get organization subscriptions with preloaded roles and permissions"""
        statement = (
            select(self.model)
            .where(
                and_(
                    self.model.organization_id == organization_id,
                    self.model.roles.any(Role.is_public.is_(True)),
                    self.model.roles.any(
                        Role.permissions.any(Permission.is_public.is_(True))
                    ),
                )
            )
            .options(
                joinedload(OrganizationSubscription.roles).joinedload(Role.permissions),
            )
        )
        return await self.list(statement)
