from wtforms import (BooleanField, EmailField, FieldList, Form, FormField,
                     IntegerField, PasswordField, SelectField, StringField,
                     validators, widgets)

from auth.forms import (ComboboxSelectField, CSRFBaseForm,
                        empty_string_to_none, get_form_field)
from auth.models import UserField
from auth.models.organization_subscription import SubscriptionStatus
from auth.models.subscription import SubscriptionTierType


class BaseUserForm(CSRFBaseForm):
    email = EmailField(
        "Email address", validators=[validators.InputRequired(), validators.Email()]
    )
    email_verified = BooleanField(
        "Email verified",
        description="You can force the email address to be verified, but make sure it actually belongs to the user.",
    )

    @classmethod
    async def get_form_class(
        cls, user_fields: list[UserField]
    ) -> type["UserCreateForm"]:
        class UserFormFields(Form):
            pass

        for field in user_fields:
            setattr(UserFormFields, field.slug, get_form_field(field))

        class UserForm(cls):  # type: ignore
            fields = FormField(UserFormFields)

        return UserForm


class UserCreateForm(BaseUserForm):
    password = PasswordField(
        "Password",
        validators=[validators.InputRequired()],
        widget=widgets.PasswordInput(hide_value=False),
    )
    tenant = ComboboxSelectField(
        "Tenant",
        query_endpoint_path="/admin/tenants/",
        validators=[validators.InputRequired(), validators.UUID()],
    )


class UserUpdateForm(BaseUserForm):
    password = PasswordField(
        "Password",
        filters=(empty_string_to_none,),
        widget=widgets.PasswordInput(hide_value=False),
    )


class UserAccessTokenForm(CSRFBaseForm):
    client = ComboboxSelectField(
        "Client",
        description="The access token will be tied to this client.",
        query_endpoint_path="/admin/clients/",
        validators=[validators.InputRequired(), validators.UUID()],
    )
    scopes = FieldList(
        StringField(validators=[validators.InputRequired()]),
        label="Scopes",
        default=["openid"],
    )


class CreateUserPermissionForm(CSRFBaseForm):
    permission = ComboboxSelectField(
        "Add new permission",
        query_endpoint_path="/admin/access-control/permissions/",
        validators=[validators.InputRequired(), validators.UUID()],
    )


class CreateUserRoleForm(CSRFBaseForm):
    role = ComboboxSelectField(
        "Add new role",
        query_endpoint_path="/admin/access-control/roles/",
        validators=[validators.InputRequired(), validators.UUID()],
    )


class OrganizationSubscriptionForm(CSRFBaseForm):
    organization = ComboboxSelectField(
        "Organization",
        query_endpoint_path="/admin/users/organizations/",
        validators=[validators.InputRequired(), validators.UUID()],
    )
    tier = ComboboxSelectField(
        "Subscription Tier",
        query_endpoint_path="/admin/subscriptions/tiers/",
        validators=[validators.InputRequired(), validators.UUID()],
    )
    status = SelectField(
        "Status",
        choices=SubscriptionStatus.choices(),
        coerce=SubscriptionStatus.coerce,
        default=SubscriptionStatus.PENDING.value,
        validators=[validators.InputRequired()],
    )
    stripe_subscription_id = StringField(
        "Stripe subscription ID",
        validators=[validators.InputRequired()],
    )
