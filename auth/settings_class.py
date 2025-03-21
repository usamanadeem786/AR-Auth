from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import (DirectoryPath, EmailStr, Field, SecretStr,
                      field_validator, model_validator)
from pydantic_settings import BaseSettings, SettingsConfigDict

from auth.crypto.encryption import is_valid_key
from auth.db.types import (DatabaseConnectionParameters, DatabaseType,
                           create_database_connection_parameters)
from auth.paths import TEMPLATES_DIRECTORY
from auth.services.email import (EMAIL_PROVIDERS, AvailableEmailProvider,
                                 EmailProvider)


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class InvalidEncryptionKeyError(ValueError):
    pass


class InitialSettings(BaseSettings):
    secrets_dir: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


initial_settings = InitialSettings()


class Settings(BaseSettings):
    environment: Environment = Environment.PRODUCTION
    log_level: str = "INFO"
    sentry_dsn_server: str | None = None
    sentry_dsn_worker: str | None = None
    telemetry_enabled: bool = False
    allow_origin_regex: str = "http://.*localhost:[0-9]+"
    port: int = 8000

    secret: SecretStr
    encryption_key: bytes

    generated_jwk_size: int = 4096

    database_type: DatabaseType = DatabaseType.SQLITE
    database_url: str | None = None
    database_host: str | None = None
    database_port: int | None = None
    database_username: str | None = None
    database_password: str | None = None
    database_name: str | None = "auth.db"
    database_ssl_mode: str | None = None
    database_location: DirectoryPath = Path.cwd()
    database_pool_recycle_seconds: int = 600
    database_pool_pre_ping: bool = False
    database_pool_size: int = 5
    database_pool_max_overflow: int = 10
    database_table_prefix: str = "auth_"

    redis_url: str = "redis://localhost:6379"

    email_provider: AvailableEmailProvider = AvailableEmailProvider.NULL
    email_provider_params: dict[str, Any] = Field(default_factory=dict)
    default_from_email: str = "contact@auth.dev"
    default_from_name: str | None = "Auth"

    csrf_check_enabled: bool = True
    csrf_cookie_name: str = "auth_csrftoken"
    csrf_cookie_secure: bool = True

    session_data_cookie_name: str = "auth_session_data"
    session_data_cookie_domain: str = ""
    session_data_cookie_secure: bool = True
    session_data_cookie_lifetime_seconds: int | None = None

    user_locale_cookie_name: str = "auth_locale"
    user_locale_cookie_domain: str = ""
    user_locale_cookie_secure: bool = True
    user_locale_lifetime_seconds: int = 86400 * 30

    login_hint_cookie_name: str = "auth_login_hint"
    login_hint_cookie_domain: str = ""
    login_hint_cookie_secure: bool = True
    login_hint_cookie_lifetime_seconds: int = 86400 * 30

    login_session_cookie_name: str = "auth_login_session"
    login_session_cookie_domain: str = ""
    login_session_cookie_secure: bool = True
    login_session_lifetime_seconds: int = 3600

    registration_session_cookie_name: str = "auth_registration_session"
    registration_session_cookie_domain: str = ""
    registration_session_cookie_secure: bool = True
    registration_session_lifetime_seconds: int = 3600

    email_verification_code_length: int = 6
    email_verification_lifetime_seconds: int = 3600

    oauth_session_lifetime_seconds: int = 3600

    session_cookie_name: str = "auth_session"
    session_cookie_domain: str = ""
    session_cookie_secure: bool = True
    session_lifetime_seconds: int = 86400 * 30

    client_redirect_uri_ssl_required: bool = True

    default_authorization_code_lifetime_seconds: int = 600
    default_access_id_token_lifetime_seconds: int = 3600 * 24
    default_refresh_token_lifetime_seconds: int = 3600 * 24 * 30

    webhooks_max_attempts: int = 5

    auth_domain: str = "localhost:8000"
    auth_client_id: str
    auth_client_secret: str
    auth_encryption_key: str | None = None
    auth_main_user_email: EmailStr | None = None
    auth_main_user_password: SecretStr | None = None
    auth_main_admin_api_key: SecretStr | None = None

    auth_admin_session_cookie_name: str = "auth_admin_session"
    auth_admin_session_cookie_domain: str = ""
    auth_admin_session_cookie_secure: bool = True

    auth_documentation_url: str = "https://docs.auth.dev"

    password_min_length: int = 8
    password_min_score: int = Field(ge=0, le=4, default=3)

    user_already_exists_cookie_name: str = "auth_user_already_exists"
    user_already_exists_cookie_domain: str = ""
    user_already_exists_cookie_secure: bool = True
    user_already_exists_cookie_lifetime_seconds: int = 60

    organization_invitation_lifetime_seconds: int = 3600 * 24 * 7

    invitation_token_cookie_name: str = "auth_invitation_token"
    invitation_token_cookie_domain: str = ""
    invitation_token_cookie_secure: bool = True
    invitation_token_cookie_lifetime_seconds: int = 3600 * 24

    # Stripe settings
    stripe_secret_key: str
    stripe_webhook_secret: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", secrets_dir=initial_settings.secrets_dir
    )

    @model_validator(mode="before")
    @classmethod
    def parse_database_url(cls, values):
        database_url = values.get("database_url")
        if database_url is not None:
            parsed_database_url = urlparse(database_url)
            values["database_host"] = parsed_database_url.hostname
            values["database_port"] = parsed_database_url.port
            values["database_username"] = parsed_database_url.username
            values["database_password"] = parsed_database_url.password
            values["database_name"] = parsed_database_url.path[1:]
        return values

    @field_validator("encryption_key", mode="before")
    @classmethod
    def validate_encryption_key(cls, value: str | None) -> bytes | None:
        if value is None:
            return value

        key = value.encode("utf-8")
        if not is_valid_key(key):
            raise InvalidEncryptionKeyError()

        return key

    @field_validator("database_port", mode="before")
    @classmethod
    def validate_empty_port(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return value

    def get_database_connection_parameters(
        self, asyncio: bool = True, schema: str | None = None
    ) -> DatabaseConnectionParameters:
        """
        Returns a proper database URL and connection arguments for async or not-async context.

        Some tools like Alembic still require a sync connection.
        """
        return create_database_connection_parameters(
            self.database_type,
            asyncio=asyncio,
            username=self.database_username,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
            path=self.database_location,
            schema=schema,
            ssl_mode=self.database_ssl_mode,
        )

    def get_email_provider(self) -> EmailProvider:
        provider_class = EMAIL_PROVIDERS[self.email_provider]
        return provider_class(**self.email_provider_params)

    def get_templates_directory(self) -> Sequence[Path]:
        return [TEMPLATES_DIRECTORY]
