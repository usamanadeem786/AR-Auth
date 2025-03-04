from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select

from auth.dependencies.pagination import (GetPaginatedObjects, Ordering,
                                          OrderingGetter, PaginatedObjects,
                                          Pagination,
                                          get_paginated_objects_getter,
                                          get_pagination)
from auth.dependencies.repositories import get_repository
from auth.models.subscription_plan import SubscriptionPlan
from auth.repositories.subscription_plan import SubscriptionPlanRepository


async def get_subscription_plan_by_id_or_404(
    id: UUID,
    repository: SubscriptionPlanRepository = Depends(
        get_repository(SubscriptionPlanRepository)
    ),
) -> SubscriptionPlan:
    subscription_plan = await repository.get_by_id(id)
    if subscription_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription plan with id {id} not found",
        )
    return subscription_plan


async def get_subscription_plan_by_plan_id_or_404(
    plan_id: UUID,
    repository: SubscriptionPlanRepository = Depends(
        get_repository(SubscriptionPlanRepository)
    ),
) -> SubscriptionPlan:
    subscription_plan = await repository.get_by_id(plan_id)
    if subscription_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subscription plan with id {id} not found",
        )
    return subscription_plan


async def get_paginated_subscription_plans(
    query: str | None = Query(None),
    pagination: Pagination = Depends(get_pagination),
    ordering: Ordering = Depends(OrderingGetter()),
    repository: SubscriptionPlanRepository = Depends(
        get_repository(SubscriptionPlanRepository)
    ),
    get_paginated_objects: GetPaginatedObjects[SubscriptionPlan] = Depends(
        get_paginated_objects_getter
    ),
) -> PaginatedObjects[SubscriptionPlan]:
    statement = select(SubscriptionPlan)
    if query:
        statement = statement.where(SubscriptionPlan.name.ilike(f"%{query}%"))

    return await get_paginated_objects(
        statement=statement,
        pagination=pagination,
        ordering=ordering,
        repository=repository,
    )


async def get_subscription_plans(
    repository: SubscriptionPlanRepository = Depends(
        get_repository(SubscriptionPlanRepository)
    ),
) -> list[SubscriptionPlan]:
    return await repository.all()
