import json

from auth_client import AuthAccessTokenMissingPermission, AuthAsync
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from auth.crypto.token import generate_token
from auth.dependencies.admin_authentication import \
    is_authenticated_admin_session
from auth.dependencies.admin_session import get_admin_session_token
from auth.dependencies.repositories import get_repository
from auth.dependencies.ssl import get_auth
from auth.models import AdminSessionToken
from auth.repositories import AdminSessionTokenRepository
from auth.services.admin import ADMIN_PERMISSION_CODENAME
from auth.settings import settings

router = APIRouter()


@router.get("/login", name="dashboard.auth:login")
async def login(
    request: Request,
    screen: str = Query("login"),
    auth: AuthAsync = Depends(get_auth),
):
    url = await auth.auth_url(
        redirect_uri=str(request.url_for("dashboard.auth:callback")),
        scope=["openid"],
        extras_params={"screen": screen},
    )
    return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)


@router.get("/callback", name="dashboard.auth:callback")
async def callback(
    request: Request,
    code: str = Query(...),
    auth: AuthAsync = Depends(get_auth),
    repository: AdminSessionTokenRepository = Depends(
        get_repository(AdminSessionTokenRepository)
    ),
):
    tokens, userinfo = await auth.auth_callback(
        code, str(request.url_for("dashboard.auth:callback"))
    )

    try:
        await auth.validate_access_token(
            tokens["access_token"], required_permissions=[ADMIN_PERMISSION_CODENAME]
        )
    except AuthAccessTokenMissingPermission as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN) from e

    token, token_hash = generate_token()
    session_token = AdminSessionToken(
        token=token_hash,
        raw_tokens=json.dumps(tokens),
        raw_userinfo=json.dumps(userinfo),
    )
    await repository.create(session_token)

    response = RedirectResponse(url="/admin/", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        settings.auth_admin_session_cookie_name,
        token,
        domain=settings.auth_admin_session_cookie_domain,
        secure=settings.auth_admin_session_cookie_secure,
        httponly=True,
    )

    return response


@router.get(
    "/profile",
    name="dashboard.auth:profile",
    dependencies=[Depends(is_authenticated_admin_session)],
)
async def profile():
    return RedirectResponse(
        url=f"//{settings.auth_domain}", status_code=status.HTTP_302_FOUND
    )


@router.get("/logout", name="dashboard.auth:logout")
async def logout(
    request: Request,
    session_token: AdminSessionToken = Depends(get_admin_session_token),
    repository: AdminSessionTokenRepository = Depends(
        get_repository(AdminSessionTokenRepository)
    ),
):
    await repository.delete(session_token)

    response = RedirectResponse(
        url=f"//{settings.auth_domain}/logout?redirect_uri={request.base_url}admin/",
        status_code=status.HTTP_302_FOUND,
    )
    response.delete_cookie(
        settings.auth_admin_session_cookie_name,
        domain=settings.auth_admin_session_cookie_domain,
        secure=settings.auth_admin_session_cookie_secure,
        httponly=True,
    )

    return response
