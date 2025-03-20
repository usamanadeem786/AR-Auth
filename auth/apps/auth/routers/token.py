from fastapi import APIRouter, Depends, Form, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import UUID4

from auth.crypto.access_token import generate_access_token
from auth.crypto.id_token import generate_id_token
from auth.crypto.token import generate_token
from auth.dependencies.logger import get_audit_logger
from auth.dependencies.permission import (
    UserPermissionsGetter,
    get_user_permissions_getter,
)
from auth.dependencies.repositories import get_repository
from auth.dependencies.tenant import get_current_tenant
from auth.dependencies.token import (
    GrantRequest,
    get_user_from_grant_request,
    validate_grant_request,
)
from auth.logger import AuditLogger
from auth.models import AuditLogMessage, RefreshToken, Tenant, User
from auth.repositories import (
    OrganizationMemberRepository,
    OrganizationSubscriptionRepository,
    RefreshTokenRepository,
)
from auth.schemas.auth import TokenResponse

router = APIRouter()


@router.post("/token", name="auth:token")
async def token(
    response: Response,
    grant_request: GrantRequest = Depends(validate_grant_request),
    user: User = Depends(get_user_from_grant_request),
    get_user_permissions: UserPermissionsGetter = Depends(get_user_permissions_getter),
    refresh_token_repository: RefreshTokenRepository = Depends(
        get_repository(RefreshTokenRepository)
    ),
    tenant: Tenant = Depends(get_current_tenant),
    organization_id: UUID4 | None = Form(None),
    organization_member_repository: OrganizationMemberRepository = Depends(
        get_repository(OrganizationMemberRepository)
    ),
    organization_subscription_repository: OrganizationSubscriptionRepository = Depends(
        get_repository(OrganizationSubscriptionRepository)
    ),
    audit_logger: AuditLogger = Depends(get_audit_logger),
):
    scope = grant_request["scope"]
    authenticated_at = grant_request["authenticated_at"]
    acr = grant_request["acr"]
    nonce = grant_request["nonce"]
    c_hash = grant_request["c_hash"]
    client = grant_request["client"]

    # Handle organization-specific permissions if organization_id is provided
    if organization_id:
        # Get organization member for the user and organization
        org_member = await organization_member_repository.get_by_user_and_org(
            user.id, organization_id
        )

        if not org_member:
            # User is not a member of this organization
            raise HTTPException(
                status_code=403,
                detail="User is not a member of the specified organization",
            )

        # Get active subscriptions for the organization
        active_subscriptions = (
            await organization_subscription_repository.get_active_by_organization(
                organization_id
            )
        )

        # Collect all subscription roles and their permissions
        subscription_permissions = set()
        permission_ids = set()

        for subscription in active_subscriptions:
            for role in subscription.roles:
                for permission in role.permissions:
                    subscription_permissions.add(permission.codename)
                    permission_ids.add(permission.id)

        # Determine permissions based on member role
        if org_member.is_owner_or_admin:
            # Owners and admins get all permissions from all subscription roles
            permissions = list(subscription_permissions)
        else:
            # Regular members only get permissions from their assigned roles
            # but these must be within the subscription roles
            member_permissions = set()

            # Only include permissions from roles that are part of active subscriptions
            for permission in org_member.permissions:
                if permission.id in permission_ids:
                    member_permissions.add(permission.codename)

            permissions = list(member_permissions)
    else:
        # Default behavior - get all user permissions
        permissions = await get_user_permissions(user)

        # Add tenant default role permissions
        for role in tenant.default_roles:
            permissions.extend([permission.codename for permission in role.permissions])

    tenant_host = tenant.get_host()
    access_token = generate_access_token(
        tenant.get_sign_jwk(),
        tenant_host,
        client,
        authenticated_at,
        acr,
        user,
        scope,
        permissions,
        client.access_id_token_lifetime_seconds,
    )
    id_token = generate_id_token(
        tenant.get_sign_jwk(),
        tenant_host,
        client,
        authenticated_at,
        acr,
        user,
        client.access_id_token_lifetime_seconds,
        nonce=nonce,
        c_hash=c_hash,
        access_token=access_token,
        encryption_key=client.get_encrypt_jwk(),
    )
    token_response = TokenResponse(
        access_token=access_token,
        id_token=id_token,
        expires_in=client.access_id_token_lifetime_seconds,
    )

    if "offline_access" in scope:
        token, token_hash = generate_token()
        refresh_token = RefreshToken(
            token=token_hash,
            scope=scope,
            user_id=user.id,
            client_id=client.id,
            authenticated_at=authenticated_at,
            expires_at=client.get_refresh_token_expires_at(),
        )
        refresh_token = await refresh_token_repository.create(refresh_token)
        token_response.refresh_token = token

    audit_logger(
        AuditLogMessage.USER_TOKEN_GENERATED,
        subject_user_id=user.id,
        grant_type=grant_request["grant_type"],
        authenticated_at=authenticated_at.isoformat(),
        scope=scope,
    )

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return token_response.model_dump(exclude_none=True)
