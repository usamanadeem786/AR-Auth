from typing import List, Optional

from pydantic import UUID4, BaseModel
from auth.schemas.generics import CreatedUpdatedAt, UUIDSchema

from auth.models.subscription import (SubscriptionInterval,
                                      SubscriptionTierMode,
                                      SubscriptionTierType)


class SubscriptionRead(UUIDSchema):
    name: str
    accounts: int

    class Config:
        from_attributes = True

class SubscriptionInfoRead(BaseModel):
    name: str
    accounts: int

    class Config:
        from_attributes = True


class TierRead(UUIDSchema):
    name: str
    mode: SubscriptionTierMode
    type: Optional[SubscriptionTierType] = None
    quantity: int
    interval: Optional[SubscriptionInterval] = None
    interval_count: Optional[int] = None

    class Config:
        from_attributes = True


class TierInfoRead(BaseModel):
    name: str
    subscription: SubscriptionInfoRead

    class Config:
        from_attributes = True


class SubscriptionWithTiers(SubscriptionRead):
    tiers: List[TierRead] = []

    class Config:
        from_attributes = True
