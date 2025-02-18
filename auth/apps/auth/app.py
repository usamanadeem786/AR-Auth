from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from auth import __version__
from auth.apps.auth.exception_handlers import exception_handlers
from auth.apps.auth.routers.auth import router as auth_router
from auth.apps.auth.routers.dashboard import router as dashboard_router
from auth.apps.auth.routers.oauth import router as oauth_router
from auth.apps.auth.routers.register import router as register_router
from auth.apps.auth.routers.reset import router as reset_router
from auth.apps.auth.routers.token import router as token_router
from auth.apps.auth.routers.user import router as user_router
from auth.apps.auth.routers.well_known import router as well_known_router
from auth.middlewares.csrf import CSRFCookieSetterMiddleware
from auth.middlewares.locale import (BabelMiddleware,
                                     get_babel_middleware_kwargs)
from auth.middlewares.security_headers import SecurityHeadersMiddleware
from auth.paths import STATIC_DIRECTORY
from auth.settings import settings


def include_routers(router: APIRouter) -> APIRouter:
    router.include_router(auth_router, include_in_schema=False)
    router.include_router(register_router, include_in_schema=False)
    router.include_router(reset_router, include_in_schema=False)
    router.include_router(token_router, prefix="/api")
    router.include_router(user_router, prefix="/api")
    router.include_router(well_known_router, prefix="/.well-known")
    router.include_router(dashboard_router, include_in_schema=False)

    return router


default_tenant_router = include_routers(APIRouter())
tenant_router = include_routers(APIRouter(prefix="/{tenant_slug}"))


app = FastAPI(title="Auth Authentication API", version=__version__)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFCookieSetterMiddleware)
app.add_middleware(GZipMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(BabelMiddleware, **get_babel_middleware_kwargs())  # type: ignore
app.include_router(oauth_router, include_in_schema=False)
app.include_router(default_tenant_router)
app.include_router(tenant_router)
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="auth:static")

for exc, handler in exception_handlers.items():
    app.add_exception_handler(exc, handler)


__all__ = ["app"]
