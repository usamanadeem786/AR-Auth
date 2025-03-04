from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select

from auth.dependencies.repositories import get_repository
from auth.models.user_subscription import UserSubscription
from auth.repositories.user_subscription import UserSubscriptionRepository


async def get_user_subscription_by_id_or_404(
    id: UUID,
    repository: UserSubscriptionRepository = Depends(
        get_repository(UserSubscriptionRepository)
    ),
) -> UserSubscription:
    user_subscription = await repository.get_by_id(id)
    if user_subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User subscription with id {id} not found",
        )
    return user_subscription


async def get_user_subscriptions_by_user_id(
    user_id: UUID,
    repository: UserSubscriptionRepository = Depends(
        get_repository(UserSubscriptionRepository)
    ),
) -> list[UserSubscription]:
    statement = select(UserSubscription).where(UserSubscription.user_id == user_id)
    return await repository.list(statement)


async def get_active_user_subscriptions_by_user_id(
    user_id: UUID,
    repository: UserSubscriptionRepository = Depends(
        get_repository(UserSubscriptionRepository)
    ),
) -> list[UserSubscription]:
    return await repository.get_active_by_user(user_id)
