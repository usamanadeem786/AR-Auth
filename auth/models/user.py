from typing import TYPE_CHECKING, Any, Optional, Self

from pydantic import UUID4
from sqlalchemy import Boolean, ForeignKey, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from auth.models.base import Base
from auth.models.generics import GUID, CreatedUpdatedAt, UUIDModel
from auth.models.tenant import Tenant
from auth.models.user_field import UserField

if TYPE_CHECKING:
    from auth.models.user_field_value import UserFieldValue
    from auth.models.user_permission import UserPermission
    from auth.models.user_role import UserRole
    from auth.models.user_subscription import UserSubscription


class User(UUIDModel, CreatedUpdatedAt, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(length=320), index=True, nullable=False, unique=True
    )
    email_lower: Mapped[str] = mapped_column(
        String(320), index=True, nullable=False, unique=True
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean, index=True, default=False, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(length=255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant_id: Mapped[UUID4] = mapped_column(
        GUID, ForeignKey(Tenant.id, ondelete="CASCADE"), nullable=False
    )
    tenant: Mapped[Tenant] = relationship("Tenant")

    user_field_values: Mapped[list["UserFieldValue"]] = relationship(
        "UserFieldValue",
        back_populates="user",
        cascade="all, delete",
        lazy="selectin",
    )

    # subscriptions: Mapped[list["UserSubscription"]] = relationship(
    #     "UserSubscription", back_populates="user", cascade="all, delete-orphan"
    # )

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email})"

    @property
    def fields(self) -> dict[str, Any]:
        return dict(
            user_field_value.get_slug_and_value()
            for user_field_value in self.user_field_values
        )

    def get_user_field_value(self, user_field: UserField) -> Optional["UserFieldValue"]:
        for user_field_value in self.user_field_values:
            if user_field_value.user_field_id == user_field.id:
                return user_field_value
        return None

    def get_claims(self) -> dict[str, Any]:
        fields = dict(
            user_field_value.get_slug_and_value(json_serializable=True)
            for user_field_value in self.user_field_values
        )
        return {
            "sub": str(self.id),
            "email": self.email,
            "email_verified": self.email_verified,
            "is_active": self.is_active,
            "tenant_id": str(self.tenant_id),
            "fields": fields,
        }

    def get_claims_with_scopes(
        self, user_roles: list["UserRole"], user_permissions: list["UserPermission"]
    ) -> dict[str, Any]:
        fields = dict(
            user_field_value.get_slug_and_value(json_serializable=True)
            for user_field_value in self.user_field_values
        )
        return {
            "sub": str(self.id),
            "email": self.email,
            "email_verified": self.email_verified,
            "is_active": self.is_active,
            "tenant_id": str(self.tenant_id),
            "fields": fields,
            "scopes": {
                "tenant": [
                    {
                        "name": str(role.display_name),
                        "permissions": [
                            {
                                "name": str(permission.name),
                                "codename": str(permission.codename),
                            }
                            for permission in role.permissions
                        ],
                    }
                    for role in self.tenant.default_roles
                ],
                "roles": [
                    {
                        "name": str(user_role.role.name),
                        "granted_by_default": str(user_role.role.granted_by_default),
                        "permissions": [
                            {
                                "name": str(permission.name),
                                "codename": str(permission.codename),
                            }
                            for permission in user_role.role.permissions
                        ],
                    }
                    for user_role in user_roles
                ],
                "permissions": [
                    {
                        "name": str(user_permission.permission.name),
                        "codename": str(user_permission.permission.codename),
                    }
                    for user_permission in user_permissions
                ],
            },
        }

    @classmethod
    def create_sample(cls, tenant: Tenant) -> Self:
        return cls(
            email="anne@bretagne.duchy",
            tenant_id=tenant.id,
        )


@event.listens_for(User.email, "set")
def update_email_lower(target: User, value: str, oldvalue, initiator):
    if value is not None:
        target.email_lower = value.lower()
