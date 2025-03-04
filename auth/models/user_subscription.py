from pydantic import UUID4
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from auth.models.base import Base
from auth.models.generics import GUID, CreatedUpdatedAt, ExpiresAt, UUIDModel
from auth.models.subscription_plan import SubscriptionPlan
from auth.models.user import User


class UserSubscription(UUIDModel, CreatedUpdatedAt, ExpiresAt, Base):
    __tablename__ = "user_subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "subscription_plan_id"),)

    user_id: Mapped[UUID4] = mapped_column(
        GUID, ForeignKey(User.id, ondelete="CASCADE"), nullable=False
    )
    subscription_plan_id: Mapped[UUID4] = mapped_column(
        GUID, ForeignKey(SubscriptionPlan.id, ondelete="CASCADE"), nullable=False
    )

    user: Mapped[User] = relationship("User")
    subscription_plan: Mapped[SubscriptionPlan] = relationship("SubscriptionPlan")
