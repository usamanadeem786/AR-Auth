from wtforms import BooleanField, EmailField, StringField, URLField, validators

from auth.forms import (
    ComboboxSelectField,
    ComboboxSelectMultipleField,
    CSRFBaseForm,
    empty_string_to_none,
)


class BaseTenantForm(CSRFBaseForm):
    name = StringField("Name", validators=[validators.InputRequired()])
    registration_allowed = BooleanField("Registration allowed", default=True)
    logo_url = URLField(
        "Logo URL",
        validators=[validators.Optional(), validators.URL(require_tld=False)],
        filters=[empty_string_to_none],
        description="It will be shown on the top left of authentication pages.",
    )
    application_url = URLField(
        "Application URL",
        validators=[validators.Optional(), validators.URL(require_tld=False)],
        filters=[empty_string_to_none],
        description="URL to your application. Used to show a link going back to your application on the user dashboard.",
    )
    theme = ComboboxSelectField(
        "UI Theme",
        query_endpoint_path="/admin/customization/themes/",
        validators=[validators.Optional(), validators.UUID()],
        filters=[empty_string_to_none],
        description="If left empty, the default theme will be used.",
    )
    oauth_providers = ComboboxSelectMultipleField(
        "OAuth Providers",
        query_endpoint_path="/admin/oauth-providers/",
        label_attr="display_name",
        choices=[],
        validate_choice=False,
        description="OAuth Providers users should be allowed to use to login.",
    )


class TenantCreateForm(BaseTenantForm):
    pass


class TenantUpdateForm(BaseTenantForm):
    pass


class TenantEmailForm(CSRFBaseForm):
    email_from_name = StringField(
        "From name",
        description="Name of the transactional emails sender.",
        validators=[],
        filters=[empty_string_to_none],
    )
    email_from_email = EmailField(
        "From email",
        description="Email address of the transactional emails sender.",
        validators=[validators.Email()],
        filters=[empty_string_to_none],
    )
