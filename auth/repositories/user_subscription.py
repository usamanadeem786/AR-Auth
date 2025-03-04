from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from auth.models.user_subscription import UserSubscription
from auth.repositories.base import BaseRepository, UUIDRepositoryMixin


class UserSubscriptionRepository(
    BaseRepository[UserSubscription], UUIDRepositoryMixin[UserSubscription]
):
    model = UserSubscription

    async def get_by_user_and_plan(
        self, user_id: UUID, subscription_plan_id: UUID
    ) -> UserSubscription | None:
        statement = select(self.model).where(
            UserSubscription.user_id == user_id,
            UserSubscription.subscription_plan_id == subscription_plan_id,
        )
        return await self.get_one_or_none(statement)

    async def get_active_by_user(self, user_id: UUID) -> list[UserSubscription]:
        now = datetime.now(UTC)
        statement = select(self.model).where(
            UserSubscription.user_id == user_id,
            (
                UserSubscription.expires_at.is_(None)
                | (UserSubscription.expires_at > now)
            ),
        )
        return await self.list(statement)

    async def create_with_expiry(
        self, user_id: UUID, subscription_plan_id: UUID, expiry_days: int | None
    ) -> UserSubscription:
        expires_at = None
        if expiry_days is not None:
            expires_at = datetime.now(UTC) + timedelta(days=expiry_days)

        user_subscription = UserSubscription(
            user_id=user_id,
            subscription_plan_id=subscription_plan_id,
            expires_at=expires_at,
        )
        return await self.create(user_subscription)
