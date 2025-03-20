from fastapi import Depends, HTTPException, Query, status
from pydantic import UUID4
from sqlalchemy import select

from auth.dependencies.pagination import (GetPaginatedObjects, Ordering,
                                          OrderingGetter, PaginatedObjects,
                                          Pagination,
                                          get_paginated_objects_getter,
                                          get_pagination)
from auth.dependencies.repositories import get_repository
from auth.models.subscription import Subscription, SubscriptionTier
from auth.repositories.subscription import (SubscriptionRepository,
                                            SubscriptionTierRepository)


async def get_subscription_by_id_or_404(
    id: UUID4,
    repository: SubscriptionRepository = Depends(
        get_repository(SubscriptionRepository)
    ),
) -> Subscription:
    subscription = await repository.get_by_id(id)
    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription with id {id} not found",
        )
    return subscription


async def get_tier_by_id_or_404(
    id: UUID4,
    repository: SubscriptionTierRepository = Depends(
        get_repository(SubscriptionTierRepository)
    ),
) -> SubscriptionTier:
    tier = await repository.get_by_id(id)
    if tier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tier with id {id} not found",
        )
    return tier


async def get_paginated_subscriptions(
    query: str | None = Query(None),
    tenant: UUID4 | None = Query(None),
    pagination: Pagination = Depends(get_pagination),
    ordering: Ordering = Depends(OrderingGetter()),
    repository: SubscriptionRepository = Depends(
        get_repository(SubscriptionRepository)
    ),
    get_paginated_objects: GetPaginatedObjects[Subscription] = Depends(
        get_paginated_objects_getter
    ),
) -> PaginatedObjects[Subscription]:
    statement = select(Subscription)
    if query:
        statement = statement.where(Subscription.name.ilike(f"%{query}%"))
    if tenant is not None:
        statement = statement.where(Subscription.tenant_id == tenant)

    return await get_paginated_objects(
        statement=statement,
        pagination=pagination,
        ordering=ordering,
        repository=repository,
    )


async def get_subscriptions(
    repository: SubscriptionRepository = Depends(
        get_repository(SubscriptionRepository)
    ),
) -> list[Subscription]:
    return await repository.all()
