from datetime import UTC, datetime, timedelta

from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from auth.models.organization import Organization
from auth.models.organization_subscription import (OrganizationSubscription,
                                                   SubscriptionStatus)
from auth.models.subscription import SubscriptionTier
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
                OrganizationSubscription.grace_expires_at > now,
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
