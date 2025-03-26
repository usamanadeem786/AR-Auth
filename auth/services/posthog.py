import functools
import hashlib
from typing import Any

from posthog import Posthog

from auth import __version__
from auth.db import AsyncSession
from auth.repositories.user import UserRepository
from auth.services.localhost import is_localhost
from auth.settings import settings

POSTHOG_API_KEY = settings.posthog_api_key

posthog = Posthog(
    POSTHOG_API_KEY,
    host=settings.posthog_host,
    disabled=not settings.telemetry_enabled,
    sync_mode=True,
)


@functools.cache
def get_server_id() -> str:
    domain = settings.auth_domain
    server_id_hash = hashlib.sha256()
    server_id_hash.update(domain.encode("utf-8"))
    server_id_hash.update(settings.secret.get_secret_value().encode("utf-8"))
    return server_id_hash.hexdigest()


async def get_server_properties(session: AsyncSession) -> dict[str, Any]:
    user_repository = UserRepository(session)
    users_count = await user_repository.count_all()
    return {
        "version": __version__,
        "is_localhost": is_localhost(settings.auth_domain),
        "database_type": settings.database_type,
        "users_count": users_count,
    }
