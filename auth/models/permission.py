from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from auth.models.base import Base
from auth.models.generics import CreatedUpdatedAt, UUIDModel


class Permission(UUIDModel, CreatedUpdatedAt, Base):
    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(String(length=255), nullable=False)
    codename: Mapped[str] = mapped_column(
        String(length=255), nullable=False, unique=True
    )

    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"Permission(id={self.id}, name={self.name}, codename={self.codename})"
