from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import UUID4
from sqlalchemy import (Column, ColumnElement, Enum, ForeignKey, Integer,
                        String, Table, UniqueConstraint)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from auth.models.base import TABLE_PREFIX, Base, get_prefixed_tablename
from auth.models.generics import (GUID, CreatedUpdatedAt, TIMESTAMPAware,
                                  UUIDModel)
from auth.models.organization import Organization
from auth.models.role import Role
from auth.models.subscription import SubscriptionInterval, SubscriptionTier


class SubscriptionStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"
    EXPIRED = "expired"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(item.value, item.value) for item in cls]

    @classmethod
    def coerce(cls, item):
        return cls(str(item)) if not isinstance(item, cls) else item


# Define the association table for organization subscription roles
OrganizationSubscriptionRole = Table(
    get_prefixed_tablename("organization_subscription_roles"),
    Base.metadata,
    Column(
        "organization_subscription_id",
        ForeignKey(
            f"{get_prefixed_tablename('organization_subscriptions')}.id",
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


class OrganizationSubscription(UUIDModel, CreatedUpdatedAt, Base):
    __tablename__ = "organization_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "tier_id",
            "stripe_subscription_id",
            "status",
        ),
    )

    tier_id: Mapped[UUID4] = mapped_column(
        GUID, ForeignKey(SubscriptionTier.id, ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[UUID4] = mapped_column(
        GUID, ForeignKey(Organization.id, ondelete="CASCADE"), nullable=False
    )
    accounts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stripe_subscription_id: Mapped[str] = mapped_column(
        String(length=255), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMPAware(timezone=True),
        nullable=True,
        index=True,
    )
    grace_period: Mapped[int] = mapped_column(Integer, default=7, nullable=True)

    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    interval: Mapped[SubscriptionInterval] = mapped_column(
        Enum(SubscriptionInterval, name=f"{TABLE_PREFIX}subscription_interval"),
        nullable=True,
    )
    interval_count: Mapped[int] = mapped_column(Integer, nullable=True)

    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name=f"{TABLE_PREFIX}subscription_status"),
        default=SubscriptionStatus.PENDING,
        nullable=False,
    )

    # Relationships
    tier: Mapped[SubscriptionTier] = relationship("SubscriptionTier")
    organization: Mapped[Organization] = relationship("Organization")
    roles: Mapped[list[Role]] = relationship(
        "Role", secondary=OrganizationSubscriptionRole, lazy="selectin"
    )

    @hybrid_property
    def grace_expires_at(self) -> datetime:
        """Calculate when the grace period expires"""
        if not self.expires_at:
            return None
        return self.expires_at + timedelta(days=self.grace_period)

    @grace_expires_at.inplace.expression
    @classmethod
    def _grace_expires_at_expression(cls) -> ColumnElement[bool]:
        return cls.expires_at + timedelta(days=cls.grace_period)

    @property
    def is_active(self) -> bool:
        """Check if the subscription is active"""
        return (
            self.status == SubscriptionStatus.ACTIVE
            or self.status == SubscriptionStatus.TRIALING
        ) and (not self.expires_at or self.expires_at > datetime.now(UTC))

    @property
    def is_in_grace_period(self) -> bool:
        """Check if the subscription is in grace period"""
        now = datetime.now(UTC)
        return (
            not self.is_active and self.expires_at < now and self.grace_expires_at > now
        )

    @property
    def days_until_expiry(self) -> int:
        """Get days until subscription expires"""
        if not self.expires_at:
            return 0
        now = datetime.now(UTC)
        if self.expires_at < now:
            return 0
        return (self.expires_at - now).days

    @property
    def days_until_grace_period_ends(self) -> int:
        """Get days until grace period ends"""
        grace_expires = self.grace_expires_at
        if not grace_expires:
            return 0
        now = datetime.now(UTC)
        if grace_expires < now:
            return 0
        return (grace_expires - now).days
