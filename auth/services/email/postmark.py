from postmarker.core import PostmarkClient
from postmarker.exceptions import ClientError

from auth.services.email.base import (
    EmailDomain,
    EmailProvider,
    SendEmailError,
    format_address,
)


class Postmark(EmailProvider):
    DOMAIN_AUTHENTICATION = False

    def __init__(self, server_token: str) -> None:
        self._client = PostmarkClient(server_token=server_token)

    def send_email(
        self,
        *,
        sender: tuple[str, str | None],
        recipient: tuple[str, str | None],
        subject: str,
        html: str | None = None,
        text: str | None = None,
    ):
        from_email, from_name = sender
        to_email, to_name = recipient
        try:
            self._client.emails.send(
                From=format_address(from_email, from_name),
                To=format_address(to_email, to_name),
                Subject=subject,
                HtmlBody=html,
                TextBody=text,
            )
        except ClientError as e:
            raise SendEmailError(str(e)) from e

    def create_domain(self, domain: str) -> EmailDomain:
        raise NotImplementedError()

    def verify_domain(self, email_domain: EmailDomain) -> EmailDomain:
        raise NotImplementedError()
