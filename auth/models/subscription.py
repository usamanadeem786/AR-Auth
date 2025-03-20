from enum import StrEnum

from pydantic import UUID4
from sqlalchemy import JSON, Boolean, Column
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from auth.models.base import TABLE_PREFIX, Base, get_prefixed_tablename
from auth.models.generics import GUID, CreatedUpdatedAt, UUIDModel
from auth.models.role import Role
from auth.models.tenant import Tenant

# Define the association table for organization subscription roles
SubscriptionRole = Table(
    get_prefixed_tablename("subscription_roles"),
    Base.metadata,
    Column(
        "subscription_id",
        ForeignKey(
            f"{get_prefixed_tablename('subscriptions')}.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    Column(
        "role_id",
        ForeignKey(f"{get_prefixed_tablename('roles')}.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Subscription(UUIDModel, CreatedUpdatedAt, Base):
    __tablename__ = "subscriptions"

    name: Mapped[str] = mapped_column(String(length=255), nullable=False)
    tenant_id: Mapped[UUID4] = mapped_column(
        GUID, ForeignKey(Tenant.id, ondelete="CASCADE"), nullable=False
    )
    stripe_product_id: Mapped[str] = mapped_column(
        String(length=255), nullable=False, unique=True
    )
    accounts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    tenant: Mapped[Tenant] = relationship("Tenant")
    roles: Mapped[list[Role]] = relationship(
        "Role", secondary=SubscriptionRole, lazy="selectin"
    )
    tiers: Mapped[list["SubscriptionTier"]] = relationship(
        "SubscriptionTier", back_populates="subscription"
    )


class SubscriptionInterval(StrEnum):
    DAY = "day"
    MONTH = "month"
    YEAR = "year"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(item.value, item.value) for item in cls]

    @classmethod
    def coerce(cls, item):
        return cls(str(item)) if not isinstance(item, cls) else item


class SubscriptionTierMode(StrEnum):
    RECURRING = "recurring"
    ONE_TIME = "one-time"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(item.value, item.value) for item in cls]

    @classmethod
    def coerce(cls, item):
        return cls(str(item)) if not isinstance(item, cls) else item


class SubscriptionTierType(StrEnum):
    PRIMARY = "primary"
    ADD_ON = "add-on"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(item.value, item.value) for item in cls]

    @classmethod
    def coerce(cls, item):
        return cls(str(item)) if not isinstance(item, cls) else item


class SubscriptionTier(UUIDModel, CreatedUpdatedAt, Base):
    __tablename__ = "subscription_tiers"

    name: Mapped[str] = mapped_column(String(length=255), nullable=False)
    subscription_id: Mapped[UUID4] = mapped_column(
        GUID, ForeignKey(Subscription.id, ondelete="CASCADE"), nullable=False
    )
    stripe_price_id: Mapped[str] = mapped_column(
        String(length=255), nullable=False, unique=True
    )
    mode: Mapped[SubscriptionTierMode] = mapped_column(
        SQLEnum(SubscriptionTierMode, name=f"{TABLE_PREFIX}subscriptiontier_mode"),
        nullable=False,
    )
    type: Mapped[SubscriptionTierType] = mapped_column(
        SQLEnum(SubscriptionTierType, name=f"{TABLE_PREFIX}subscriptiontier_type"),
        nullable=True,
    )
    interval: Mapped[SubscriptionInterval] = mapped_column(
        SQLEnum(SubscriptionInterval, name=f"{TABLE_PREFIX}subscription_interval"),
        nullable=True,
    )
    interval_count: Mapped[int] = mapped_column(Integer, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Relationships
    subscription: Mapped[Subscription] = relationship(
        "Subscription", back_populates="tiers"
    )


class SubscriptionEventStatus(StrEnum):
    NORMAL = "normal"
    CRITICAL = "critical"


class SubscriptionEvent(UUIDModel, CreatedUpdatedAt, Base):
    __tablename__ = "subscription_events"

    event_id: Mapped[str] = mapped_column(
        String(length=255), nullable=False, unique=True
    )
    type: Mapped[str] = mapped_column(String(length=255), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default={})
    error: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[SubscriptionEventStatus] = mapped_column(
        SQLEnum(SubscriptionEventStatus, name=f"{TABLE_PREFIX}subscriptionevent_status"),
        default=SubscriptionEventStatus.NORMAL,
        nullable=False,
    )
