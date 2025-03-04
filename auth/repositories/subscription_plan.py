from sqlalchemy import select

from auth.models.subscription_plan import SubscriptionPlan
from auth.repositories.base import BaseRepository, UUIDRepositoryMixin


class SubscriptionPlanRepository(
    BaseRepository[SubscriptionPlan], UUIDRepositoryMixin[SubscriptionPlan]
):
    model = SubscriptionPlan

    async def get_by_name(self, name: str) -> SubscriptionPlan | None:
        statement = select(self.model).where(SubscriptionPlan.name == name)
        return await self.get_one_or_none(statement)

    async def get_default_plans(self) -> list[SubscriptionPlan]:
        statement = select(self.model).where(
            SubscriptionPlan.granted_by_default == True
        )
        return await self.list(statement)
