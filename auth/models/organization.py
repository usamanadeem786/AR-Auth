from enum import StrEnum
from typing import TYPE_CHECKING, Optional

from pydantic import UUID4
from sqlalchemy import Boolean, Column, Enum, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.schema import UniqueConstraint

from auth.models.base import TABLE_PREFIX, Base, get_prefixed_tablename
from auth.models.generics import GUID, CreatedUpdatedAt, ExpiresAt, UUIDModel
from auth.models.permission import Permission
from auth.models.user import User
from auth.settings import settings

if TYPE_CHECKING:
    from auth.models.permission import Permission
    from auth.models.user import User


class OrganizationMemberRole(StrEnum):
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
    role: Mapped[OrganizationMemberRole] = mapped_column(
        Enum(OrganizationMemberRole, name=f"{TABLE_PREFIX}organizationmemberrole"),
        index=True,
        nullable=False,
        default=OrganizationMemberRole.MEMBER,
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
        return self.role == OrganizationMemberRole.OWNER

    @property
    def is_admin(self) -> bool:
        return self.role == OrganizationMemberRole.ADMIN

    @property
    def is_member(self) -> bool:
        return self.role == OrganizationMemberRole.MEMBER

    @property
    def is_owner_or_admin(self) -> bool:
        return self.role in [OrganizationMemberRole.OWNER, OrganizationMemberRole.ADMIN]

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
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="invitations"
    )
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission", secondary=OrganizationInvitationPermission, lazy="selectin"
    )
