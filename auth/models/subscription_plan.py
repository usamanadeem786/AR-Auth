from enum import StrEnum

from pydantic import UUID4
from sqlalchemy import (Boolean, Column, Enum, ForeignKey, Integer, String,
                        Table, Text, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from auth.models.base import TABLE_PREFIX, Base, get_prefixed_tablename
from auth.models.generics import GUID, CreatedUpdatedAt, UUIDModel
from auth.models.role import Role
from auth.models.tenant import Tenant


class SubscriptionPlanExpiryUnit(StrEnum):
    DAY = "day"
    DAYS = "days"
    MONTH = "month"
    MONTHS = "months"
    YEAR = "year"
    YEARS = "years"

    def get_display_name(self) -> str:
        display_names = {
            SubscriptionPlanExpiryUnit.DAY: "Day",
            SubscriptionPlanExpiryUnit.DAYS: "Days",
            SubscriptionPlanExpiryUnit.MONTH: "Month",
            SubscriptionPlanExpiryUnit.MONTHS: "Months",
            SubscriptionPlanExpiryUnit.YEAR: "Year",
            SubscriptionPlanExpiryUnit.YEARS: "Years",
        }
        return display_names[self]

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.get_display_name()) for member in cls]

    @classmethod
    def coerce(cls, item):
        return cls(str(item)) if not isinstance(item, cls) else item


# Define the association table for subscription plan roles
SubscriptionPlanRole = Table(
    get_prefixed_tablename("subscription_plan_roles"),
    Base.metadata,
    Column(
        "subscription_plan_id",
        ForeignKey(
            f"{get_prefixed_tablename('subscription_plans')}.id", ondelete="CASCADE"
        ),
        primary_key=True,
    ),
    Column(
        "role_id",
        ForeignKey(f"{get_prefixed_tablename("roles")}.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class SubscriptionPlan(UUIDModel, CreatedUpdatedAt, Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (UniqueConstraint("name", "tenant_id"),)

    name: Mapped[str] = mapped_column(String(length=255), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_by_default: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    expiry_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    expiry_unit: Mapped[SubscriptionPlanExpiryUnit] = mapped_column(
        Enum(
            SubscriptionPlanExpiryUnit,
            name=f"{TABLE_PREFIX}subscriptionplanexpiryunit",
        ),
        index=True,
        nullable=False,
        default=SubscriptionPlanExpiryUnit.MONTH,
    )

    tenant_id: Mapped[UUID4] = mapped_column(
        GUID, ForeignKey(Tenant.id, ondelete="CASCADE"), nullable=False
    )
    tenant: Mapped[Tenant] = relationship("Tenant")

    roles: Mapped[list[Role]] = relationship(
        "Role",
        secondary=SubscriptionPlanRole,
        lazy="selectin",
    )
