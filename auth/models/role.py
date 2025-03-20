from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from auth.models.base import Base, get_prefixed_tablename
from auth.models.generics import CreatedUpdatedAt, UUIDModel
from auth.models.permission import Permission

if TYPE_CHECKING:
    from auth.models.user_permission import UserPermission

RolePermission = Table(
    get_prefixed_tablename("roles_permissions"),
    Base.metadata,
    Column(
        "role_id",
        ForeignKey(f"{get_prefixed_tablename('roles')}.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        ForeignKey(f"{get_prefixed_tablename('permissions')}.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(UUIDModel, CreatedUpdatedAt, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(length=255), nullable=False)
    granted_by_default: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    permissions: Mapped[list[Permission]] = relationship(
        "Permission", secondary=RolePermission, lazy="selectin"
    )
    user_permissions: Mapped[list["UserPermission"]] = relationship(
        "UserPermission", cascade="all, delete"
    )

    def __repr__(self) -> str:
        return f"Role(id={self.id}, name={self.name}, granted_by_default={self.granted_by_default}"

    @property
    def display_name(self) -> str:
        return self.name
