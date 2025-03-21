from enum import StrEnum


class EmailTemplateType(StrEnum):
    BASE = "BASE"
    WELCOME = "WELCOME"
    VERIFY_EMAIL = "VERIFY_EMAIL"
    FORGOT_PASSWORD = "FORGOT_PASSWORD"
    ORGANIZATION_INVITATION = "ORGANIZATION_INVITATION"
    SUBSCRIPTION_GRACE_PERIOD = "SUBSCRIPTION_GRACE_PERIOD"
    SUBSCRIPTION_EXPIRED = "SUBSCRIPTION_EXPIRED"

    def get_display_name(self) -> str:
        display_names = {
            EmailTemplateType.BASE: "Base",
            EmailTemplateType.WELCOME: "Welcome",
            EmailTemplateType.VERIFY_EMAIL: "Verify email",
            EmailTemplateType.FORGOT_PASSWORD: "Forgot password",
            EmailTemplateType.ORGANIZATION_INVITATION: "Organization invitation",
            EmailTemplateType.SUBSCRIPTION_GRACE_PERIOD: "Subscription grace period",
            EmailTemplateType.SUBSCRIPTION_EXPIRED: "Subscription expired",
        }
        return display_names[self]
