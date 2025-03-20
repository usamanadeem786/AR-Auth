from fastapi import APIRouter, Depends, Query
from pydantic import UUID4

from auth.dependencies.repositories import get_repository
from auth.dependencies.tenant import get_current_tenant
from auth.dependencies.users import current_active_user
from auth.models import Tenant, User
from auth.repositories.subscription import SubscriptionRepository
from auth.schemas.subscription import SubscriptionWithTiers

router = APIRouter(prefix="/subscriptions", tags=["subscription"])


@router.get(
    "",
    response_model=list[SubscriptionWithTiers],
)
async def list_subscriptions(
    current_user: User = Depends(current_active_user),
    tenant: Tenant = Depends(get_current_tenant),
    subscription_repository: SubscriptionRepository = Depends(
        get_repository(SubscriptionRepository)
    ),
):
    """List subscriptions with their tiers - requires authentication"""
    subscriptions = await subscription_repository.get_all_public_by_tenant(tenant.id)
    return [
        SubscriptionWithTiers.model_validate(subscription).model_dump(
            exclude_unset=True, exclude_none=True
        )
        for subscription in subscriptions
    ]
