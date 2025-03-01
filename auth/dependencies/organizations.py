from typing import Any

from fastapi import Depends, HTTPException, Query, status
from fastapi.exceptions import RequestValidationError
from pydantic import UUID4, ValidationError, create_model
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from auth import schemas
from auth.dependencies.logger import get_audit_logger
from auth.dependencies.pagination import (GetPaginatedObjects, Ordering,
                                          OrderingGetter, PaginatedObjects,
                                          Pagination,
                                          get_paginated_objects_getter,
                                          get_pagination)
from auth.dependencies.repositories import get_repository
from auth.dependencies.request import get_request_json
from auth.dependencies.tasks import get_send_task
from auth.dependencies.users import current_active_user
from auth.dependencies.webhooks import TriggerWebhooks, get_trigger_webhooks
from auth.logger import AuditLogger
from auth.models import (Organization, OrganizationInvitation,
                         OrganizationMember)
from auth.repositories.organization import (OrganizationInvitationRepository,
                                            OrganizationMemberRepository,
                                            OrganizationRepository)
from auth.repositories.permission import PermissionRepository
from auth.services.organization_manager import (OrganizationManager,
                                                OrganizationNotFoundError)
from auth.tasks import SendTask


async def get_organization_manager(
    organization_repository: OrganizationRepository = Depends(
        get_repository(OrganizationRepository)
    ),
    member_repository: OrganizationMemberRepository = Depends(
        get_repository(OrganizationMemberRepository)
    ),
    invitation_repository: OrganizationInvitationRepository = Depends(
        get_repository(OrganizationInvitationRepository)
    ),
    permission_repository: PermissionRepository = Depends(
        get_repository(PermissionRepository)
    ),
    send_task: SendTask = Depends(get_send_task),
    audit_logger: AuditLogger = Depends(get_audit_logger),
    trigger_webhooks: TriggerWebhooks = Depends(get_trigger_webhooks),
) -> OrganizationManager:
    return OrganizationManager(
        organization_repository=organization_repository,
        member_repository=member_repository,
        invitation_repository=invitation_repository,
        permission_repository=permission_repository,
        send_task=send_task,
        audit_logger=audit_logger,
        trigger_webhooks=trigger_webhooks,
    )


async def get_paginated_organizations(
    current_user=Depends(current_active_user),
    query: str | None = Query(None),
    pagination: Pagination = Depends(get_pagination),
    ordering: Ordering = Depends(OrderingGetter()),
    repository: OrganizationRepository = Depends(
        get_repository(OrganizationRepository)
    ),
    get_paginated_objects: GetPaginatedObjects[Organization] = Depends(
        get_paginated_objects_getter
    ),
) -> PaginatedObjects[Organization]:
    # Base query for organizations
    statement = select(Organization)

    # Get organizations where user is a member
    member_orgs = select(OrganizationMember.organization_id).where(
        OrganizationMember.user_id == str(current_user.id)
    )
    statement = statement.where(Organization.id.in_(member_orgs))

    # Apply name search filter if provided
    if query is not None:
        statement = statement.where(Organization.name.ilike(f"%{query}%"))

    return await get_paginated_objects(statement, pagination, ordering, repository)


async def get_organization_by_id_or_404(
    id: UUID4,
    current_user=Depends(current_active_user),
    organization_manager: OrganizationManager = Depends(get_organization_manager),
) -> Organization:
    try:
        organization = (
            await organization_manager.organization_repository.get_by_id_and_member(
                id, current_user.id
            )
        )
        if not organization:
            raise OrganizationNotFoundError()
        return organization

    except OrganizationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


async def get_paginated_organization_members(
    id: UUID4,
    query: str | None = Query(None),
    pagination: Pagination = Depends(get_pagination),
    ordering: Ordering = Depends(OrderingGetter()),
    member_repository: OrganizationMemberRepository = Depends(
        get_repository(OrganizationMemberRepository)
    ),
    get_paginated_objects: GetPaginatedObjects[OrganizationMember] = Depends(
        get_paginated_objects_getter
    ),
) -> PaginatedObjects[OrganizationMember]:
    statement = (
        select(OrganizationMember)
        .options(joinedload(OrganizationMember.user))
        .where(OrganizationMember.organization_id == str(id))
    )
    if query is not None:
        statement = statement.where(
            OrganizationMember.user.has(name__ilike=f"%{query}%")
        )
    return await get_paginated_objects(
        statement, pagination, ordering, member_repository
    )


async def get_organization_member_by_id_or_404(
    organization_id: UUID4,
    user_id: UUID4,
    member_repository: OrganizationMemberRepository = Depends(
        get_repository(OrganizationMemberRepository)
    ),
) -> OrganizationMember:
    member = await member_repository.get_by_user_and_org(
        str(user_id), str(organization_id)
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return member


async def get_paginated_organization_invitations(
    id: UUID4,
    query: str | None = Query(None),
    pagination: Pagination = Depends(get_pagination),
    ordering: Ordering = Depends(OrderingGetter()),
    organization: Organization = Depends(get_organization_by_id_or_404),
    invitation_repository: OrganizationInvitationRepository = Depends(
        get_repository(OrganizationInvitationRepository)
    ),
    get_paginated_objects: GetPaginatedObjects[OrganizationInvitation] = Depends(
        get_paginated_objects_getter
    ),
) -> PaginatedObjects[OrganizationInvitation]:
    statement = select(OrganizationInvitation).where(
        OrganizationInvitation.organization_id == organization.id
    )
    if query is not None:
        statement = statement.where(OrganizationInvitation.email.ilike(f"%{query}%"))
    return await get_paginated_objects(
        statement, pagination, ordering, invitation_repository
    )


async def get_organization_invitation_by_id_or_404(
    invitation_id: UUID4,
    invitation_repository: OrganizationInvitationRepository = Depends(
        get_repository(OrganizationInvitationRepository)
    ),
) -> OrganizationInvitation:
    invitation = await invitation_repository.get_by_id(invitation_id)
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return invitation


async def validate_organization_data(
    json: dict[str, Any] = Depends(get_request_json),
    model: type[
        schemas.organization.OrganizationCreate
        | schemas.organization.OrganizationUpdate
    ] = None,
) -> schemas.organization.OrganizationCreate | schemas.organization.OrganizationUpdate:
    body_model = create_model(
        "OrganizationBody",
        body=(model, ...),
    )
    try:
        validated_data = body_model(body=json)
    except ValidationError as e:
        raise RequestValidationError(e.errors()) from e
    return validated_data.body


async def check_organization_permission(
    permission_codename: str,
    organization: Organization,
    user_id: UUID4,
    organization_manager: OrganizationManager,
) -> bool:
    """Check if user has specific organization permission"""
    organization_member = (
        await organization_manager.member_repository.get_by_user_and_org(
            str(user_id), str(organization.id)
        )
    )
    if organization_member:
        if organization_member.is_owner_or_admin:
            return True
        elif organization_member.is_member:
            if permission_codename in organization_member.permissions_codenames:
                return True

    return False


def require_organization_permission(
    permission_codename: str,
):
    async def _require_organization_permission(
        organization: Organization = Depends(get_organization_by_id_or_404),
        current_user=Depends(current_active_user),
        organization_manager: OrganizationManager = Depends(get_organization_manager),
    ):
        has_permission = await check_organization_permission(
            permission_codename, organization, current_user.id, organization_manager
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to perform this action",
            )
        return organization

    return _require_organization_permission
