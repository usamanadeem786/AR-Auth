import secrets
from typing import Optional

from pydantic import UUID4
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from auth.models.organization import (Organization, OrganizationInvitation,
                                      OrganizationMember)
from auth.models.permission import Permission
from auth.models.user import User
from auth.repositories.base import (BaseRepository, ExpiresAtMixin,
                                    UUIDRepositoryMixin)


class OrganizationRepository(
    BaseRepository[Organization], UUIDRepositoryMixin[Organization]
):
    model = Organization

    async def get_by_user_and_org(
        self, user_id: str, organization_id: str
    ) -> Optional[Organization]:
        statement = select(self.model).where(
            self.model.user_id == user_id, self.model.id == organization_id
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_user_and_org_name(
        self, user_id: str, organization_name: str
    ) -> Optional[Organization]:
        statement = select(self.model).where(
            self.model.user_id == user_id, self.model.name == organization_name
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_user_and_org_ids(
        self, user_id: str, organization_ids: list[UUID4]
    ) -> list[Organization]:
        statement = select(self.model).where(
            self.model.user_id == user_id, self.model.id.in_(organization_ids)
        )
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_by_id_and_member(
        self, id: UUID4, user_id: str
    ) -> Optional[Organization]:
        statement = select(self.model).where(
            self.model.id == id,
            self.model.members.any(OrganizationMember.user_id == user_id),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_user_with_tenant(self, user_id: UUID4) -> Optional[User]:
        """Get user with tenant relationship loaded"""
        stmt = select(User).options(joinedload(User.tenant)).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_customer_id(
        self, stripe_customer_id: str
    ) -> Optional[Organization]:
        """Get organization by user's Stripe customer ID"""
        statement = select(self.model).where(
            self.model.user.has(User.stripe_customer_id == stripe_customer_id),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()


class OrganizationMemberRepository(
    BaseRepository[OrganizationMember], UUIDRepositoryMixin[OrganizationMember]
):
    model = OrganizationMember

    async def get_by_user(self, user_id: UUID4) -> list[OrganizationMember]:
        statement = (
            select(self.model)
            .where(self.model.user_id == user_id)
            .options(
                joinedload(OrganizationMember.organization).joinedload(
                    Organization.subscriptions
                )
            )
        )
        return await self.list(statement)

    async def get_by_user_and_org(
        self, user_id: str, organization_id: str
    ) -> Optional[OrganizationMember]:
        statement = (
            select(self.model)
            .where(
                self.model.user_id == user_id,
                self.model.organization_id == organization_id,
            )
            .options(joinedload(self.model.user))
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_user_and_org_ids(
        self, user_id: str, organization_ids: list[UUID4]
    ) -> list[OrganizationMember]:
        statement = select(self.model).where(
            self.model.user_id == user_id,
            self.model.organization_id.in_(organization_ids),
        )
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def get_by_organization(
        self, organization_id: UUID4
    ) -> list[OrganizationMember]:
        """Get all members of an organization"""
        statement = select(self.model).where(
            self.model.organization_id == organization_id
        )
        result = await self.session.execute(statement)
        return result.scalars().all()


class OrganizationInvitationRepository(
    BaseRepository[OrganizationInvitation],
    UUIDRepositoryMixin[OrganizationInvitation],
    ExpiresAtMixin[OrganizationInvitation],
):
    model = OrganizationInvitation

    async def get_by_email_and_org(
        self, email: str, organization_id: UUID4
    ) -> Optional[OrganizationInvitation]:
        statement = select(self.model).where(
            self.model.email == email, self.model.organization_id == organization_id
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_token(self, token: str) -> Optional[OrganizationInvitation]:
        statement = (
            select(self.model)
            .where(self.model.token == token)
            .options(joinedload(self.model.organization))
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_id(self, id: UUID4) -> Optional[OrganizationInvitation]:
        """Get invitation by ID"""
        statement = (
            select(self.model)
            .where(self.model.id == id)
            .options(joinedload(self.model.organization))
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def count_by_organization(self, organization_id: UUID4) -> int:
        statement = select(self.model).where(
            self.model.organization_id == organization_id
        )
        return await self._count(statement)
