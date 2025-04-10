import secrets
from enum import StrEnum
from typing import TYPE_CHECKING, Optional

from pydantic import UUID4
from sqlalchemy import Boolean, Column, Enum, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.schema import UniqueConstraint

from auth.models.base import TABLE_PREFIX, Base, get_prefixed_tablename
from auth.models.client import Client
from auth.models.generics import (GUID, CreatedUpdatedAt, ExpiresAt,
                                  PydanticUrlString, UUIDModel)
from auth.models.permission import Permission
from auth.models.user import User
from auth.settings import settings

if TYPE_CHECKING:
    from auth.models.organization_subscription import OrganizationSubscription


class OrganizationRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


# Association table for organization member permissions
OrganizationMemberPermission = Table(
    get_prefixed_tablename("organization_member_permissions"),
    Base.metadata,
    Column(
        "member_id",
        ForeignKey(
            f"{get_prefixed_tablename('organization_members')}.id", ondelete="CASCADE"
        ),
        primary_key=True,
    ),
    Column(
        "permission_id",
        ForeignKey(f"{get_prefixed_tablename('permissions')}.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Add this new association table
OrganizationInvitationPermission = Table(
    get_prefixed_tablename("organization_invitation_permissions"),
    Base.metadata,
    Column(
        "invitation_id",
        ForeignKey(
            f"{get_prefixed_tablename('organization_invitations')}.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    ),
    Column(
        "permission_id",
        ForeignKey(f"{get_prefixed_tablename('permissions')}.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Organization(UUIDModel, CreatedUpdatedAt, Base):
    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    user_id: Mapped[UUID4] = mapped_column(
        GUID,
        ForeignKey(f"{get_prefixed_tablename('users')}.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User")
    # Relationships
    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        lazy="selectin",
        cascade="all, delete",
    )
    invitations: Mapped[list["OrganizationInvitation"]] = relationship(
        "OrganizationInvitation", back_populates="organization", cascade="all, delete"
    )
    subscriptions: Mapped[list["OrganizationSubscription"]] = relationship(
        "OrganizationSubscription",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    def get_active_primary_subscription(self) -> "OrganizationSubscription | None":
        """
        Get the active primary subscription for this organization.

        Returns:
            The active primary subscription, or None if not found
        """
        from auth.models.organization_subscription import SubscriptionType

        for subscription in self.subscriptions:
            if (
                subscription.subscription_type == SubscriptionType.PRIMARY
                and subscription.is_active
            ):
                return subscription
        return None

    def get_member_limit(self) -> int:
        """
        Get the maximum number of members allowed for this organization
        based on its active primary subscription.

        Returns:
            int: The member limit (defaults to 1 if no active subscription)
        """
        primary_subscription = self.get_active_primary_subscription()
        if primary_subscription:
            return primary_subscription.member_limit
        return 1  # Default limit if no active subscription

    def get_current_member_count(self) -> int:
        """
        Get the current number of members in this organization.

        Returns:
            int: The number of members
        """
        return self.members.count()

    def can_add_member(self) -> bool:
        """
        Check if the organization can add another member
        based on its subscription limit.

        Returns:
            bool: True if a member can be added, False otherwise
        """
        return self.get_current_member_count() < self.get_member_limit()

    def get_remaining_seats(self) -> int:
        """
        Get the number of remaining seats available for new members.

        Returns:
            int: The number of remaining seats (0 if at or over limit)
        """
        limit = self.get_member_limit()
        current = self.get_current_member_count()
        return max(0, limit - current)


class OrganizationMember(UUIDModel, CreatedUpdatedAt, Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)

    organization_id: Mapped[UUID4] = mapped_column(
        GUID,
        ForeignKey(f"{get_prefixed_tablename('organizations')}.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID4] = mapped_column(
        GUID,
        ForeignKey(f"{get_prefixed_tablename('users')}.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole, name=f"{TABLE_PREFIX}organizationrole"),
        index=True,
        nullable=False,
        default=OrganizationRole.MEMBER,
    )

    # Relationships
    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="members"
    )
    user: Mapped["User"] = relationship("User")
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission", secondary=OrganizationMemberPermission, lazy="selectin"
    )

    @property
    def is_owner(self) -> bool:
        return self.role == OrganizationRole.OWNER

    @property
    def is_admin(self) -> bool:
        return self.role == OrganizationRole.ADMIN

    @property
    def is_member(self) -> bool:
        return self.role == OrganizationRole.MEMBER

    @property
    def is_owner_or_admin(self) -> bool:
        return self.role in [OrganizationRole.OWNER, OrganizationRole.ADMIN]

    @property
    def permissions_codenames(self) -> list[str]:
        return [permission.codename for permission in self.permissions]

    @property
    def permissions_ids(self) -> list[UUID4]:
        return [permission.id for permission in self.permissions]


class OrganizationInvitation(UUIDModel, CreatedUpdatedAt, ExpiresAt, Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (UniqueConstraint("organization_id", "email"),)
    __lifetime_seconds__ = settings.organization_invitation_lifetime_seconds

    organization_id: Mapped[UUID4] = mapped_column(
        GUID,
        ForeignKey(f"{get_prefixed_tablename('organizations')}.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[OrganizationRole] = mapped_column(
        Enum(OrganizationRole, name=f"{TABLE_PREFIX}organizationrole"),
        index=True,
        nullable=False,
        default=OrganizationRole.MEMBER,
    )
    token: Mapped[str] = mapped_column(
        String(255),
        default=secrets.token_urlsafe,
        unique=True,
        index=True,
        nullable=False,
    )
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="invitations"
    )
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission", secondary=OrganizationInvitationPermission, lazy="selectin"
    )

    # Client relation
    client_id: Mapped[UUID4] = mapped_column(
        GUID,
        ForeignKey(f"{get_prefixed_tablename('clients')}.id", ondelete="CASCADE"),
        nullable=False,
    )
    client: Mapped["Client"] = relationship("Client", lazy="joined")
    redirect_uri: Mapped[str | None] = mapped_column(
        PydanticUrlString(String)(length=512), default=None, nullable=True
    )
