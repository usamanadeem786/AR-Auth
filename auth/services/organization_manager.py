from datetime import UTC, datetime, timedelta

from fastapi import Request
from furl import furl
from pydantic import UUID4

from auth import schemas
from auth.dependencies.webhooks import TriggerWebhooks
from auth.logger import AuditLogger
from auth.models import (AuditLogMessage, Client, Organization,
                         OrganizationInvitation, OrganizationMember,
                         OrganizationRole, Tenant)
from auth.repositories.organization import (OrganizationInvitationRepository,
                                            OrganizationMemberRepository,
                                            OrganizationRepository)
from auth.repositories.permission import PermissionRepository
from auth.services.webhooks.models import (OrganizationCreated,
                                           OrganizationDeleted,
                                           OrganizationInvitationAccepted,
                                           OrganizationInvitationCreated,
                                           OrganizationInvitationResend,
                                           OrganizationInvitationRevoked,
                                           OrganizationMemberPermissionAdded,
                                           OrganizationMemberPermissionRemoved,
                                           OrganizationMemberRemoved,
                                           OrganizationUpdated)
from auth.settings import settings
from auth.tasks import SendTask, on_after_organization_invitation


class OrganizationManagerError(Exception):
    """Base exception for organization manager errors."""

    pass


class OrganizationNotFoundError(OrganizationManagerError):
    """Raised when an organization is not found."""

    pass


class OrganizationAlreadyExistsError(OrganizationManagerError):
    """Raised when attempting to create an organization that already exists."""

    pass


class OrganizationMemberNotFoundError(OrganizationManagerError):
    """Raised when a member is not found in the organization."""

    pass


class OrganizationMemberAlreadyExistsError(OrganizationManagerError):
    """Raised when a member already exists in the organization."""

    pass


class OrganizationMemberPermissionNotFoundError(OrganizationManagerError):
    """Raised when a permission is not found for a member."""

    pass


class OrganizationMemberPermissionAlreadyExistsError(OrganizationManagerError):
    """Raised when a permission already exists for a member."""

    pass


class InvalidInvitationError(OrganizationManagerError):
    """Base class for invitation-related errors."""

    pass


class InvitationExpiredError(InvalidInvitationError):
    """Raised when an invitation has expired."""

    pass


class InvitationAlreadyAcceptedError(InvalidInvitationError):
    """Raised when an invitation has already been accepted."""

    pass


class InvitationEmailMismatchError(InvalidInvitationError):
    """Raised when the invitation email doesn't match the user's email."""

    pass


class InvitationAlreadyExistsError(InvalidInvitationError):
    """Raised when the invitation already exists."""

    pass


class InvitationMaxLimitReachedError(InvalidInvitationError):
    """Raised when the invitation max limit has been reached."""

    pass


class OrganizationAccessDeniedError(OrganizationManagerError):
    """Raised when a user doesn't have access to an organization."""

    pass


class ClientNotFoundError(OrganizationManagerError):
    """Raised when a client is not found."""

    pass


class InvalidClientRedirectUriError(OrganizationManagerError):
    """Raised when a client redirect URI is invalid."""

    pass


class OrganizationManager:
    def __init__(
        self,
        *,
        organization_repository: OrganizationRepository,
        member_repository: OrganizationMemberRepository,
        invitation_repository: OrganizationInvitationRepository,
        permission_repository: PermissionRepository,
        send_task: SendTask,
        audit_logger: AuditLogger,
        trigger_webhooks: TriggerWebhooks,
    ):
        self.organization_repository = organization_repository
        self.member_repository = member_repository
        self.invitation_repository = invitation_repository
        self.permission_repository = permission_repository
        self.send_task = send_task
        self.audit_logger = audit_logger
        self.trigger_webhooks = trigger_webhooks

    async def get(self, id: UUID4) -> Organization:
        """Get organization by ID"""
        organization = await self.organization_repository.get_by_id(id)
        if organization is None:
            raise OrganizationNotFoundError()
        return organization

    async def create(
        self,
        organization_create: schemas.organization.OrganizationCreate,
        user_id: UUID4,
    ) -> Organization:
        """Create new organization and add creator as owner"""
        # Already exists
        organization = await self.organization_repository.get_by_user_and_org_name(
            user_id, organization_create.name
        )
        if organization:
            raise OrganizationAlreadyExistsError()

        organization = Organization(user_id=user_id, **organization_create.model_dump())
        organization = await self.organization_repository.create(organization)

        # Add creator as owner
        member = OrganizationMember(
            organization_id=organization.id,
            user_id=user_id,
            role=OrganizationRole.OWNER,
        )
        await self.member_repository.create(member)

        await self.on_after_create(organization)
        return organization

    async def update(
        self,
        organization_update: schemas.organization.OrganizationUpdate,
        organization: Organization,
    ) -> Organization:
        """Update organization details"""
        organization_update_dict = organization_update.model_dump(exclude_unset=True)
        for field, value in organization_update_dict.items():
            setattr(organization, field, value)

        await self.organization_repository.update(organization)
        await self.on_after_update(organization)
        return organization

    async def delete(
        self,
        organization: Organization,
    ) -> None:
        """Delete organization and all related data"""
        await self.organization_repository.delete(organization)
        await self.on_after_delete(organization)

    async def remove_member(
        self,
        organization: Organization,
        user_id: UUID4,
    ) -> None:
        """Remove member from organization"""
        member = await self.member_repository.get_by_user_and_org(
            str(user_id), str(organization.id)
        )
        if member is None:
            raise OrganizationMemberNotFoundError()

        await self.member_repository.delete(member)

        invitation = await self.invitation_repository.get_by_email_and_org(
            member.user.email, organization.id
        )
        if invitation:
            await self.invitation_repository.delete(invitation)

        await self.on_after_member_removed(member)

    async def add_permission(
        self,
        organization: Organization,
        user_id: UUID4,
        permission_id: UUID4,
    ) -> None:
        """Add a permission to a member"""
        member = await self.member_repository.get_by_user_and_org(
            str(user_id), str(organization.id)
        )
        if member is None:
            raise OrganizationMemberNotFoundError()

        if permission_id in member.permissions_ids:
            raise OrganizationMemberPermissionAlreadyExistsError()

        permission = await self.permission_repository.get_by_id(permission_id)
        if permission is None:
            raise OrganizationMemberPermissionNotFoundError()

        member.permissions.append(permission)
        await self.member_repository.update(member)
        await self.on_after_member_permission_added(member)

    async def remove_permission(
        self,
        organization: Organization,
        user_id: UUID4,
        permission_id: UUID4,
    ) -> None:
        """Remove a permission from a member"""
        member = await self.member_repository.get_by_user_and_org(
            str(user_id), str(organization.id)
        )
        if member is None:
            raise OrganizationMemberNotFoundError()

        if permission_id not in member.permissions_ids:
            raise OrganizationMemberPermissionNotFoundError()

        permission = await self.permission_repository.get_by_id(permission_id)
        if permission is None:
            raise OrganizationMemberPermissionNotFoundError()

        member.permissions.remove(permission)
        await self.member_repository.update(member)
        await self.on_after_member_permission_deleted(member)

    async def create_invitation(
        self,
        request: Request,
        accounts: int,
        organization: Organization,
        invitation_create: schemas.organization.OrganizationInvitationCreate,
        tenant: Tenant,
        client: Client,
    ) -> OrganizationInvitation:
        """Create and send organization invitation"""
        total_invitations = await self.invitation_repository.count_by_organization(
            organization.id
        )
        if total_invitations >= accounts:
            raise InvitationMaxLimitReachedError()

        invitation_exists = await self.invitation_repository.get_by_email_and_org(
            invitation_create.email, organization.id
        )
        if invitation_exists:
            raise InvitationAlreadyExistsError()

        if invitation_create.permissions:
            permissions = await self.permission_repository.get_by_ids(
                invitation_create.permissions
            )
        else:
            permissions = []

        # Create invitation with organization reference
        invitation = await self.invitation_repository.create(
            OrganizationInvitation(
                organization_id=str(organization.id),
                email=invitation_create.email,
                permissions=permissions,
                client_id=client.id,
                redirect_uri=invitation_create.redirect_uri,
            )
        )
        await self.on_after_invitation_created(
            request, invitation, tenant, organization.name
        )
        return invitation

    async def revoke_invitation(
        self,
        invitation: OrganizationInvitation,
    ) -> None:
        """Revoke an organization invitation"""
        await self.invitation_repository.delete(invitation)
        await self.on_after_invitation_revoked(invitation)

    async def resend_invitation(
        self,
        request: Request,
        invitation: OrganizationInvitation,
        tenant: Tenant,
    ) -> None:
        """Resend an organization invitation"""
        # Reset expiry time
        invitation.expires_at = datetime.now(UTC) + timedelta(
            seconds=settings.organization_invitation_lifetime_seconds
        )
        await self.invitation_repository.update(invitation)

        # Get organization and user info for email
        organization = await self.organization_repository.get_by_id(
            invitation.organization_id
        )
        await self.on_after_invitation_resend(
            request, invitation, tenant, organization.name
        )
        return invitation

    async def get_invitation_by_token(self, token: str) -> OrganizationInvitation:
        """Get invitation"""

        invitation = await self.invitation_repository.get_by_token(token)
        if invitation is None:
            raise InvalidInvitationError()

        # Check if expired
        if invitation.is_expired:
            raise InvitationExpiredError()

        # Check if already accepted
        if invitation.accepted:
            raise InvitationAlreadyAcceptedError()

        return invitation

    async def accept_invitation(
        self,
        token: str,
        user_id: UUID4,
    ) -> OrganizationInvitation:
        """Accept invitation and add member"""
        # Get and validate invitation
        invitation = await self.get_invitation_by_token(token)

        try:
            # Get user to check email match
            user = await self.organization_repository.get_user_with_tenant(user_id)
            if user.email != invitation.email:
                raise InvitationEmailMismatchError()

            # Check if user is already a member
            existing_member = await self.member_repository.get_by_user_and_org(
                str(user_id), str(invitation.organization_id)
            )
            if existing_member is not None:
                raise OrganizationMemberAlreadyExistsError()

            # Create member with basic role
            member = OrganizationMember(
                organization_id=invitation.organization_id,
                user_id=user_id,
                role=invitation.role,
            )
            member = await self.member_repository.create(member)

            # Assign direct permissions
            if invitation.permissions:
                permissions = await self.permission_repository.get_by_ids(
                    invitation.permissions
                )
                member.permissions.extend(permissions)
                await self.member_repository.update(member)

            # Mark invitation as accepted
            invitation.accepted = True
            await self.invitation_repository.update(invitation)
            await self.on_after_invitation_accepted(invitation)

            return invitation

        except Exception as e:
            # Re-raise known exceptions directly
            if isinstance(
                e,
                (
                    InvitationEmailMismatchError,
                    OrganizationMemberAlreadyExistsError,
                    InvalidInvitationError,
                ),
            ):
                raise
            # Otherwise wrap in a general InvalidInvitationError
            raise InvalidInvitationError() from e

    # Event handlers
    async def on_after_create(
        self,
        organization: Organization,
    ):
        self.audit_logger(
            AuditLogMessage.ORGANIZATION_CREATED,
            object_id=str(organization.id),
        )
        self.trigger_webhooks(
            OrganizationCreated, organization, schemas.organization.Organization
        )

    async def on_after_update(
        self,
        organization: Organization,
    ):
        self.audit_logger(
            AuditLogMessage.ORGANIZATION_UPDATED,
            object_id=str(organization.id),
        )
        self.trigger_webhooks(
            OrganizationUpdated, organization, schemas.organization.Organization
        )

    async def on_after_delete(
        self,
        organization: Organization,
    ):
        self.audit_logger(
            AuditLogMessage.OBJECT_DELETED,
            object_id=str(organization.id),
        )
        self.trigger_webhooks(
            OrganizationDeleted, organization, schemas.organization.Organization
        )

    async def on_after_member_permission_added(
        self,
        member: OrganizationMember,
    ):
        self.audit_logger(
            AuditLogMessage.OBJECT_UPDATED,
            object_id=str(member.organization_id),
        )
        self.trigger_webhooks(
            OrganizationMemberPermissionAdded,
            member,
            schemas.organization.OrganizationMember,
        )

    async def on_after_member_permission_deleted(
        self,
        member: OrganizationMember,
    ):
        self.audit_logger(
            AuditLogMessage.OBJECT_UPDATED,
            object_id=str(member.organization_id),
        )
        self.trigger_webhooks(
            OrganizationMemberPermissionRemoved,
            member,
            schemas.organization.OrganizationMember,
        )

    async def on_after_member_removed(
        self,
        member: OrganizationMember,
    ):
        self.audit_logger(
            AuditLogMessage.OBJECT_UPDATED,
            object_id=str(member.organization_id),
            user_id=str(member.user_id),
        )
        self.trigger_webhooks(
            OrganizationMemberRemoved,
            member,
            schemas.organization.OrganizationMember,
        )

    async def on_after_invitation_revoked(
        self,
        invitation: OrganizationInvitation,
    ):
        self.audit_logger(
            AuditLogMessage.ORGANIZATION_INVITATION_REVOKED,
            object_id=str(invitation.organization_id),
            email=invitation.email,
        )
        self.trigger_webhooks(
            OrganizationInvitationRevoked,
            invitation,
            schemas.organization.OrganizationInvitation,
        )

    async def on_after_invitation_accepted(
        self,
        invitation: OrganizationInvitation,
    ):
        self.audit_logger(
            AuditLogMessage.ORGANIZATION_INVITATION_ACCEPTED,
            object_id=str(invitation.id),
            email=invitation.email,
        )
        self.trigger_webhooks(
            OrganizationInvitationAccepted,
            invitation,
            schemas.organization.OrganizationInvitation,
        )

    async def on_after_invitation_created(
        self,
        request: Request,
        invitation: OrganizationInvitation,
        tenant: Tenant,
        organization_name: str,
    ):
        self.audit_logger(
            AuditLogMessage.OBJECT_CREATED,
            object_id=str(invitation.organization_id),
            email=invitation.email,
        )
        self.trigger_webhooks(
            OrganizationInvitationCreated,
            invitation,
            schemas.organization.OrganizationInvitation,
        )
        invitation_url = furl(tenant.url_for(request, "invitation:accept"))
        invitation_url.add(query_params={"token": invitation.token})

        # Send invitation email asynchronously
        self.send_task(
            on_after_organization_invitation,
            invitation.email,
            str(tenant.id),
            organization_name,
            invitation_url.url,
        )

    async def on_after_invitation_resend(
        self,
        request: Request,
        invitation: OrganizationInvitation,
        tenant: Tenant,
        organization_name: str,
    ):
        self.audit_logger(
            AuditLogMessage.ORGANIZATION_INVITATION_RESEND,
            object_id=str(invitation.organization_id),
            email=invitation.email,
        )
        self.trigger_webhooks(
            OrganizationInvitationResend,
            invitation,
            schemas.organization.OrganizationInvitation,
        )

        invitation_url = furl(tenant.url_for(request, "invitation:accept"))
        invitation_url.add(query_params={"token": invitation.token})

        # Send invitation email asynchronously
        self.send_task(
            on_after_organization_invitation,
            invitation.email,
            str(tenant.id),
            organization_name,
            invitation_url.url,
        )
