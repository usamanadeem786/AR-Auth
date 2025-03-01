from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse

from auth.apps.auth.forms.invitation import AcceptInvitationForm
from auth.dependencies.auth import BaseContext, get_base_context
from auth.dependencies.organizations import get_organization_manager
from auth.dependencies.session_token import get_session_token
from auth.dependencies.tenant import get_current_tenant
from auth.errors import APIErrorCode
from auth.forms import FormHelper
from auth.locale import gettext_lazy as _
from auth.models import SessionToken, Tenant
from auth.services.organization_manager import (
    InvalidInvitationError, InvitationAlreadyAcceptedError,
    InvitationEmailMismatchError, InvitationExpiredError, OrganizationManager,
    OrganizationMemberAlreadyExistsError)
from auth.settings import settings

router = APIRouter()


@router.api_route(
    "/accept",
    methods=["GET", "POST"],
    name="invitation:accept",
)
async def accept_invitation(
    request: Request,
    token: str | None = Query(None),
    organization_manager: OrganizationManager = Depends(get_organization_manager),
    tenant: Tenant = Depends(get_current_tenant),
    session_token: SessionToken | None = Depends(get_session_token),
    context: BaseContext = Depends(get_base_context),
):

    form_helper = FormHelper(
        AcceptInvitationForm,
        "auth/accept_invitation.html",
        request=request,
        context={**context},
    )
    form = await form_helper.get_form()

    try:
        # Handle GET request - load organization name
        if request.method == "GET":
            if token is None:
                return await form_helper.get_error_response(
                    _("The invitation token is missing."),
                    "missing_token",
                    fatal=True,
                )

            form.token.data = token
            invitation = await organization_manager.get_invitation_by_token(token)
            form_helper.context["organization_name"] = invitation.organization.name

            # If user is not logged in, redirect to login page with invitation token
            if session_token is None:
                response = RedirectResponse(
                    url=tenant.url_path_for(request, "auth:login"),
                    status_code=status.HTTP_302_FOUND,
                )
                response.set_cookie(
                    settings.invitation_token_cookie_name,
                    token,
                    max_age=settings.invitation_token_cookie_lifetime_seconds,
                    domain=settings.invitation_token_cookie_domain,
                    secure=settings.invitation_token_cookie_secure,
                    httponly=True,
                )
                return response

        # Handle POST request - accept invitation
        if request.method == "POST" and await form_helper.is_submitted_and_valid():
            await organization_manager.accept_invitation(
                form.token.data, session_token.user_id
            )
            return RedirectResponse(
                url=f"{tenant.application_url}?invitation_accepted",
                status_code=status.HTTP_302_FOUND,
            )

        return await form_helper.get_response()

    except InvitationExpiredError:
        return await form_helper.get_error_response(
            _("This invitation has expired."),
            APIErrorCode.ORGANIZATION_INVITATION_EXPIRED,
            fatal=True,
        )
    except InvitationEmailMismatchError:
        return await form_helper.get_error_response(
            _(
                "This invitation is for a different email address, Please login with the correct email address."
            ),
            APIErrorCode.ORGANIZATION_INVITATION_EMAIL_MISMATCH,
            fatal=True,
        )
    except InvitationAlreadyAcceptedError:
        return await form_helper.get_error_response(
            _("This invitation has already been accepted."),
            APIErrorCode.ORGANIZATION_INVITATION_ALREADY_ACCEPTED,
            fatal=True,
        )
    except OrganizationMemberAlreadyExistsError:
        return await form_helper.get_error_response(
            _("You are already a member of this organization."),
            APIErrorCode.ORGANIZATION_MEMBER_ALREADY_EXISTS,
            fatal=True,
        )
    except InvalidInvitationError:
        return await form_helper.get_error_response(
            _("This invitation is not valid."),
            APIErrorCode.ORGANIZATION_INVITATION_INVALID,
            fatal=True,
        )
