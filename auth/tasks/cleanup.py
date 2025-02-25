import dramatiq

from auth.repositories import (
    AuthorizationCodeRepository,
    EmailVerificationRepository,
    LoginSessionRepository,
    OAuthSessionRepository,
    RefreshTokenRepository,
    RegistrationSessionRepository,
    SessionTokenRepository,
    # OrganizationInvitationRepository,
)
from auth.repositories.base import ExpiresAtRepositoryProtocol
from auth.tasks.base import TaskBase

repository_classes: list[type[ExpiresAtRepositoryProtocol]] = [
    AuthorizationCodeRepository,
    EmailVerificationRepository,
    LoginSessionRepository,
    OAuthSessionRepository,
    RefreshTokenRepository,
    RegistrationSessionRepository,
    SessionTokenRepository,
    # OrganizationInvitationRepository,
]


class CleanupTask(TaskBase):
    __name__ = "cleanup"

    async def run(self):
        async with self.get_main_session() as session:
            for repository_class in repository_classes:
                repository = repository_class(session)
                await repository.delete_expired()


cleanup = dramatiq.actor(CleanupTask())
