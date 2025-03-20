from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from auth.models.subscription import (Subscription, SubscriptionEvent,
                                      SubscriptionTier)
from auth.repositories.base import BaseRepository, UUIDRepositoryMixin


class SubscriptionRepository(
    BaseRepository[Subscription], UUIDRepositoryMixin[Subscription]
):
    model = Subscription

    async def get_all_public_by_tenant(self, tenant_id: UUID4) -> list[Subscription]:
        statement = (
            select(self.model)
            .where(
                self.model.tenant_id == tenant_id,
                self.model.is_public == True,
                self.model.tiers.any(SubscriptionTier.is_public == True),
            )
            .options(joinedload(self.model.tiers))
        )
        return await self.list(statement)

    async def get_by_name(self, name: str) -> Subscription | None:
        statement = select(self.model).where(self.model.name == name)
        return await self.get_one_or_none(statement)

    async def get_by_tenant(self, tenant_id: UUID4) -> list[Subscription]:
        statement = (
            select(self.model)
            .where(self.model.tenant_id == tenant_id)
            .options(joinedload(self.model.tiers))
        )
        return await self.list(statement)


class SubscriptionTierRepository(
    BaseRepository[SubscriptionTier], UUIDRepositoryMixin[SubscriptionTier]
):
    model = SubscriptionTier

    async def get_by_subscription(
        self, subscription_id: UUID4
    ) -> list[SubscriptionTier]:
        statement = (
            select(self.model)
            .where(self.model.subscription_id == subscription_id)
            .options(joinedload(self.model.subscription))
        )
        return await self.list(statement)

    async def get_with_subscription_by_id(self, id: UUID4) -> SubscriptionTier | None:
        statement = (
            select(self.model)
            .where(self.model.id == id)
            .options(joinedload(self.model.subscription))
        )
        return await self.get_one_or_none(statement)

    async def get_by_stripe_price_id(
        self, stripe_price_id: str
    ) -> SubscriptionTier | None:
        statement = (
            select(self.model)
            .where(self.model.stripe_price_id == stripe_price_id)
            .options(joinedload(self.model.subscription))
        )
        return await self.get_one_or_none(statement)

    async def get_all_with_subscription(self) -> list[SubscriptionTier]:
        statement = select(self.model).options(joinedload(self.model.subscription))
        return await self.list(statement)


class SubscriptionEventRepository(
    BaseRepository[SubscriptionEvent], UUIDRepositoryMixin[SubscriptionEvent]
):
    model = SubscriptionEvent
