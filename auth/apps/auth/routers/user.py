from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from auth.dependencies.repositories import get_repository
from auth.dependencies.users import (current_active_user,
                                     current_active_user_acr_level_1,
                                     current_user, get_user_manager,
                                     get_user_update)
from auth.errors import APIErrorCode
from auth.models import OrganizationRole, User
from auth.models.organization_subscription import SubscriptionStatus
from auth.repositories import OrganizationMemberRepository
from auth.schemas.organization import OrganizationSubscriptionCalculated
from auth.schemas.user import (UF, UserChangeEmail, UserChangePassword,
                               UserUpdate, UserVerifyEmail)
from auth.services.user_manager import (InvalidEmailVerificationCodeError,
                                        InvalidPasswordError,
                                        UserAlreadyExistsError, UserManager)

router = APIRouter()


@router.api_route("/userinfo", methods=["GET", "POST"], name="user:userinfo")
async def userinfo(
    user: User = Depends(current_active_user),
    organization_member_repository: OrganizationMemberRepository = Depends(
        get_repository(OrganizationMemberRepository)
    ),
):
    """
    OpenID specification requires the /userinfo endpoint
    to be available both with GET and POST methods 🤷‍♂️
    https://openid.net/specs/openid-connect-core-1_0.html#UserInfoRequest
    """
    # Get basic user claims
    user_claims = user.get_claims()

    # Get all organization memberships for the user
    organization_memberships = await organization_member_repository.get_by_user(user.id)

    # Categorize organizations
    owned_organizations = []
    member_organizations = []

    for membership in organization_memberships:
        org_info = {
            "id": str(membership.organization_id),
            "name": membership.organization.name,
            "role": membership.role.value,
        }

        org_info["subscription"] = [
            OrganizationSubscriptionCalculated.model_validate(subscription)
            for subscription in membership.organization.subscriptions
            if subscription.status == SubscriptionStatus.ACTIVE
        ]

        if membership.role == OrganizationRole.OWNER:
            owned_organizations.append(org_info)
        else:
            member_organizations.append(org_info)

    # Add organization information to the user claims
    user_claims["organizations"] = {
        "owned": owned_organizations,
        "memberships": member_organizations,
    }

    return user_claims


@router.patch(
    "/profile",
    name="user:profile.patch",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": UserUpdate.model_json_schema(
                        ref_template="#/paths/~1api~1profile/patch/requestBody/content/application~1json/schema/definitions/{model}"
                    )
                }
            },
            "required": True,
        }
    },
)
async def update_profile(
    request: Request,
    user_update: UserUpdate[UF] = Depends(get_user_update),
    user: User = Depends(current_user()),
    user_manager: UserManager = Depends(get_user_manager),
):
    user = await user_manager.update(user_update, user, request=request)
    return user.get_claims()


@router.patch("/password", name="user:password")
async def change_password(
    request: Request,
    change_password: UserChangePassword,
    user: User = Depends(current_active_user_acr_level_1),
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        user = await user_manager.change_password(
            change_password.password.get_secret_value(), user, request=request
        )
    except InvalidPasswordError as e:
        # Build a JSON response manually to fine-tune the response structure
        return JSONResponse(
            content={
                "detail": APIErrorCode.USER_UPDATE_INVALID_PASSWORD,
                "reason": [str(message) for message in e.messages],
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    else:
        return user.get_claims()


@router.patch(
    "/email/change", name="user:email_change", status_code=status.HTTP_202_ACCEPTED
)
async def email_change(
    request: Request,
    change_email: UserChangeEmail,
    user: User = Depends(current_active_user_acr_level_1),
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        await user_manager.request_verify_email(
            user, change_email.email, request=request
        )
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=APIErrorCode.USER_UPDATE_EMAIL_ALREADY_EXISTS,
        ) from e
    else:
        return user.get_claims()


@router.post("/email/verify", name="user:email_verify")
async def email_verify(
    request: Request,
    verify_email: UserVerifyEmail,
    user: User = Depends(current_active_user_acr_level_1),
    user_manager: UserManager = Depends(get_user_manager),
):
    try:
        user = await user_manager.verify_email(
            user, verify_email.code.get_secret_value(), request=request
        )
    except InvalidEmailVerificationCodeError as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=APIErrorCode.USER_UPDATE_INVALID_EMAIL_VERIFICATION_CODE,
        ) from e
    else:
        return user.get_claims()
