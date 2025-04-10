from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import UUID4

from auth import schemas
from auth.dependencies.organizations import (
    get_organization_by_id_or_404, get_organization_invitation_by_id_or_404,
    get_organization_manager, get_paginated_organization_invitations,
    get_paginated_organization_members, get_paginated_organizations,
    require_organization_permission)
from auth.dependencies.pagination import PaginatedObjects
from auth.dependencies.repositories import get_repository
from auth.dependencies.tenant import get_current_tenant
from auth.dependencies.users import current_active_user
from auth.errors import APIErrorCode
from auth.models import (Organization, OrganizationInvitation,
                         OrganizationMember, Tenant, User)
from auth.repositories import ClientRepository
from auth.repositories.organization_subscription import \
    OrganizationSubscriptionRepository
from auth.schemas.generics import PaginatedResults
from auth.services.organization import (
    ORGANIZATION_DELETE_CODENAME, ORGANIZATION_INVITE_CODENAME,
    ORGANIZATION_INVITE_LIST_CODENAME, ORGANIZATION_INVITE_RESEND_CODENAME,
    ORGANIZATION_INVITE_REVOKE_CODENAME, ORGANIZATION_MEMBER_LIST_CODENAME,
    ORGANIZATION_MEMBER_PERMISSION_ADD_CODENAME,
    ORGANIZATION_MEMBER_PERMISSION_REMOVE_CODENAME,
    ORGANIZATION_MEMBER_REMOVE_CODENAME, ORGANIZATION_PERMISSION_LIST_CODENAME,
    ORGANIZATION_UPDATE_CODENAME)
from auth.services.organization_manager import (
    ClientNotFoundError, InvalidClientRedirectUriError, InvalidInvitationError,
    InvitationAlreadyExistsError, InvitationMaxLimitReachedError,
    OrganizationAlreadyExistsError, OrganizationManager,
    OrganizationMemberAlreadyExistsError, OrganizationMemberNotFoundError,
    OrganizationMemberPermissionAlreadyExistsError,
    OrganizationMemberPermissionNotFoundError)

router = APIRouter(prefix="/organizations", tags=["organizations"])


# Organization endpoints
@router.get(
    "",
    response_model=PaginatedResults[schemas.organization.Organization],
)
async def list_organizations(
    paginated_organizations: PaginatedObjects[Organization] = Depends(
        get_paginated_organizations
    ),
):
    """List organizations where user is a member"""
    organizations, count = paginated_organizations

    return PaginatedResults(
        count=count,
        results=[
            schemas.organization.Organization.model_validate(organization)
            for organization in organizations
        ],
    )


@router.post(
    "",
    response_model=schemas.organization.Organization,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization(
    organization_create: schemas.organization.OrganizationCreate,
    current_user=Depends(current_active_user),
    organization_manager: OrganizationManager = Depends(get_organization_manager),
):
    """Create new organization - any authenticated user can create"""
    try:
        organization = await organization_manager.create(
            organization_create, current_user.id
        )
    except OrganizationAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=APIErrorCode.ORGANIZATION_CREATE_ALREADY_EXISTS,
        )
    return schemas.organization.OrganizationRead.model_validate(organization)


@router.get(
    "/{id:uuid}",
    response_model=schemas.organization.Organization,
)
async def get_organization(
    organization: Organization = Depends(get_organization_by_id_or_404),
):
    """Get organization details - accessible by any member"""
    return schemas.organization.OrganizationRead.model_validate(organization)


@router.patch(
    "/{id:uuid}",
    response_model=schemas.organization.Organization,
)
async def update_organization(
    organization_update: schemas.organization.OrganizationUpdate,
    organization: Organization = Depends(
        require_organization_permission(ORGANIZATION_UPDATE_CODENAME)
    ),
    organization_manager: OrganizationManager = Depends(get_organization_manager),
):
    """Update organization - requires update permission"""
    return await organization_manager.update(organization_update, organization)


@router.delete(
    "/{id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_organization(
    organization: Organization = Depends(
        require_organization_permission(ORGANIZATION_DELETE_CODENAME)
    ),
    organization_manager: OrganizationManager = Depends(get_organization_manager),
):
    """Delete organization - requires delete permission"""
    await organization_manager.delete(organization)


# Member endpoints
@router.get(
    "/{id:uuid}/members",
    response_model=PaginatedResults[schemas.organization.OrganizationMember],
)
async def list_organization_members(
    organization: Organization = Depends(
        require_organization_permission(ORGANIZATION_MEMBER_LIST_CODENAME)
    ),
    paginated_members: PaginatedObjects[OrganizationMember] = Depends(
        get_paginated_organization_members
    ),
):
    """List organization members - requires membership"""
    members, count = paginated_members
    return PaginatedResults(
        count=count,
        results=[
            schemas.organization.OrganizationMember.model_validate(member)
            for member in members
        ],
    )


@router.delete(
    "/{id:uuid}/members/{user_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_organization_member(
    user_id: UUID4,
    organization: Organization = Depends(
        require_organization_permission(ORGANIZATION_MEMBER_REMOVE_CODENAME)
    ),
    organization_manager: OrganizationManager = Depends(get_organization_manager),
):
    """Remove member from organization - requires member management permission"""
    try:
        await organization_manager.remove_member(organization, user_id)
    except OrganizationMemberNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=APIErrorCode.ORGANIZATION_MEMBER_NOT_FOUND,
        )


# Member permission endpoints
@router.post(
    "/{id:uuid}/members/{user_id:uuid}/permissions",
    status_code=status.HTTP_201_CREATED,
)
async def add_member_permission(
    user_id: UUID4,
    permission_create: schemas.organization.OrganizationMemberPermissionCreate,
    organization: Organization = Depends(
        require_organization_permission(ORGANIZATION_MEMBER_PERMISSION_ADD_CODENAME)
    ),
    organization_manager: OrganizationManager = Depends(get_organization_manager),
):
    """Add permission to member - requires permission management permission"""
    try:
        await organization_manager.add_permission(
            organization,
            user_id,
            permission_create.permission_id,
        )
    except OrganizationMemberNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=APIErrorCode.ORGANIZATION_MEMBER_NOT_FOUND,
        )
    except OrganizationMemberPermissionAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=APIErrorCode.ORGANIZATION_MEMBER_PERMISSION_ALREADY_EXISTS,
        )


@router.delete(
    "/{id:uuid}/members/{user_id:uuid}/permissions/{permission_id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member_permission(
    user_id: UUID4,
    permission_id: UUID4,
    organization: Organization = Depends(
        require_organization_permission(ORGANIZATION_MEMBER_PERMISSION_REMOVE_CODENAME)
    ),
    organization_manager: OrganizationManager = Depends(get_organization_manager),
):
    """Remove permission from member - requires permission management permission"""
    try:
        await organization_manager.remove_permission(
            organization,
            user_id,
            permission_id,
        )
    except OrganizationMemberNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=APIErrorCode.ORGANIZATION_MEMBER_NOT_FOUND,
        )
    except OrganizationMemberPermissionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=APIErrorCode.ORGANIZATION_MEMBER_PERMISSION_NOT_FOUND,
        )


# Invitation endpoints
@router.get(
    "/{id:uuid}/invitations",
    response_model=PaginatedResults[schemas.organization.OrganizationInvitation],
)
async def list_organization_invitations(
    organization: Organization = Depends(
        require_organization_permission(ORGANIZATION_INVITE_LIST_CODENAME)
    ),
    paginated_invitations: PaginatedObjects[OrganizationInvitation] = Depends(
        get_paginated_organization_invitations
    ),
):
    """List organization invitations - requires membership"""
    invitations, count = paginated_invitations
    return PaginatedResults(
        count=count,
        results=[
            schemas.organization.OrganizationInvitation.model_validate(invitation)
            for invitation in invitations
        ],
    )


@router.post(
    "/{id:uuid}/invitations",
    response_model=schemas.organization.OrganizationInvitationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_organization_invitation(
    request: Request,
    invitation_create: schemas.organization.OrganizationInvitationCreate,
    organization: Organization = Depends(
        require_organization_permission(ORGANIZATION_INVITE_CODENAME)
    ),
    organization_manager: OrganizationManager = Depends(get_organization_manager),
    tenant: Tenant = Depends(get_current_tenant),
    client_repository: ClientRepository = Depends(get_repository(ClientRepository)),
    organization_subscription_repository: OrganizationSubscriptionRepository = Depends(
        get_repository(OrganizationSubscriptionRepository)
    ),
):
    """Create invitation - requires invite permission"""
    try:
        client = await client_repository.get_by_client_id(invitation_create.client_id)
        if client is None:
            raise ClientNotFoundError()
        if invitation_create.redirect_uri is not None:
            if not str(invitation_create.redirect_uri) in client.redirect_uris:
                raise InvalidClientRedirectUriError()

        accounts = await organization_subscription_repository.get_organization_accounts(
            organization.id
        )

        await organization_manager.create_invitation(
            request, accounts, organization, invitation_create, tenant, client
        )
    except (
        InvalidInvitationError,
        OrganizationMemberAlreadyExistsError,
        InvitationAlreadyExistsError,
        InvitationMaxLimitReachedError,
        ClientNotFoundError,
        InvalidClientRedirectUriError,
    ) as e:
        if isinstance(e, OrganizationMemberAlreadyExistsError):
            error_code = APIErrorCode.ORGANIZATION_MEMBER_ALREADY_EXISTS
        elif isinstance(e, InvitationAlreadyExistsError):
            error_code = APIErrorCode.ORGANIZATION_INVITATION_ALREADY_EXISTS
        elif isinstance(e, InvitationMaxLimitReachedError):
            error_code = APIErrorCode.ORGANIZATION_INVITATION_MAX_LIMIT_REACHED
        elif isinstance(e, ClientNotFoundError):
            error_code = APIErrorCode.CLIENT_NOT_FOUND
        elif isinstance(e, InvalidClientRedirectUriError):
            error_code = APIErrorCode.CLIENT_INVALID_REDIRECT_URI
        else:
            error_code = APIErrorCode.ORGANIZATION_INVITATION_INVALID

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_code,
        )
    return invitation_create.model_dump(exclude={"client_id", "redirect_uri"})


@router.delete(
    "/{id:uuid}/invitations/{invitation_id:uuid}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_organization_invitation(
    invitation: OrganizationInvitation = Depends(
        get_organization_invitation_by_id_or_404
    ),
    organization: Organization = Depends(
        require_organization_permission(ORGANIZATION_INVITE_REVOKE_CODENAME)
    ),
    organization_manager: OrganizationManager = Depends(get_organization_manager),
):
    """Revoke invitation - requires invite management permission"""
    try:
        if invitation.organization_id != organization.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        await organization_manager.revoke_invitation(invitation)
    except InvalidInvitationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=APIErrorCode.ORGANIZATION_INVITATION_INVALID,
        )


@router.post(
    "/{id:uuid}/invitations/{invitation_id:uuid}/resend",
    status_code=status.HTTP_200_OK,
)
async def resend_organization_invitation(
    request: Request,
    invitation: OrganizationInvitation = Depends(
        get_organization_invitation_by_id_or_404
    ),
    organization: Organization = Depends(
        require_organization_permission(ORGANIZATION_INVITE_RESEND_CODENAME)
    ),
    organization_manager: OrganizationManager = Depends(get_organization_manager),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Resend invitation - requires invite management permission"""
    try:
        if invitation.organization_id != organization.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        await organization_manager.resend_invitation(request, invitation, tenant)
    except InvalidInvitationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=APIErrorCode.ORGANIZATION_INVITATION_INVALID,
        )
    return {"message": "Invitation resent successfully"}


# Subscription endpoints
@router.get(
    "/{id:uuid}/subscriptions",
    response_model=list[schemas.organization.OrganizationSubscriptionRead],
)
async def list_organization_subscriptions(
    organization: Organization = Depends(get_organization_by_id_or_404),
    user: User = Depends(current_active_user),
    organization_subscription_repository: OrganizationSubscriptionRepository = Depends(
        get_repository(OrganizationSubscriptionRepository)
    ),
):
    """List organization subscriptions - accessible by any member"""
    if organization.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the organization owner can access the subscription details",
        )

    subscriptions = (
        await organization_subscription_repository.get_by_organization_and_user(
            organization.id, user.id
        )
    )

    return [
        schemas.organization.OrganizationSubscriptionRead.model_validate(subscription)
        for subscription in subscriptions
    ]


@router.get(
    "/{id:uuid}/permissions",
    response_model=list[schemas.organization.RolePermission],
)
async def list_organization_subscription_permissions(
    organization: Organization = Depends(
        require_organization_permission(ORGANIZATION_PERMISSION_LIST_CODENAME)
    ),
    user: User = Depends(current_active_user),
    organization_subscription_repository: OrganizationSubscriptionRepository = Depends(
        get_repository(OrganizationSubscriptionRepository)
    ),
):
    """List permissions available through organization subscriptions - accessible by any member"""

    # Get all subscriptions for the organization with preloaded public roles and permissions
    subscriptions = await organization_subscription_repository.get_by_organization_with_roles_permissions(
        organization.id
    )

    # Build a list of roles with permissions - the query already filtered for public roles and permissions
    result = []
    for subscription in subscriptions:
        for role in subscription.roles:
            # Create schema objects directly from the filtered data
            permissions = [
                schemas.organization.PermissionInfo.model_validate(permission)
                for permission in role.permissions
            ]

            if permissions:
                result.append(
                    schemas.organization.RolePermission(
                        name=role.name, permissions=permissions
                    )
                )

    return result
