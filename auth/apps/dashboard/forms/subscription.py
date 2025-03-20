from wtforms import (BooleanField, IntegerField, SelectField, StringField,
                     TextAreaField, validators)

from auth.forms import (ComboboxSelectField, ComboboxSelectMultipleField,
                        CSRFBaseForm)
from auth.models.organization_subscription import SubscriptionStatus
from auth.models.subscription import (SubscriptionInterval,
                                      SubscriptionTierMode,
                                      SubscriptionTierType)


class BaseSubscriptionForm(CSRFBaseForm):
    name = StringField("Name", validators=[validators.InputRequired()])
    accounts = IntegerField(
        "Accounts Limit",
        validators=[validators.InputRequired()],
        default=1,
        description="Maximum number of members allowed for organizations with this subscription.",
    )
    stripe_product_id = StringField(
        "Stripe Product ID",
        validators=[validators.InputRequired()],
        description="The Stripe product ID for this subscription.",
    )
    is_public = BooleanField("Public", default=True)

    roles = ComboboxSelectMultipleField(
        "Roles",
        query_endpoint_path="/admin/access-control/roles/",
        label_attr="display_name",
        validators=[validators.InputRequired()],
        choices=[],
        validate_choice=False,
        description="Roles that will be granted to users with this subscription.",
    )


class SubscriptionCreateForm(BaseSubscriptionForm):
    tenant = ComboboxSelectField(
        "Tenant",
        query_endpoint_path="/admin/tenants/",
        validators=[validators.InputRequired(), validators.UUID()],
    )


class SubscriptionUpdateForm(BaseSubscriptionForm):
    pass


class SubscriptionTierForm(CSRFBaseForm):
    name = StringField("Name", validators=[validators.InputRequired()])
    mode = SelectField(
        "Mode",
        choices=SubscriptionTierMode.choices(),
        coerce=SubscriptionTierMode.coerce,
        default=SubscriptionTierMode.RECURRING.value,
        validators=[validators.InputRequired()],
        description="Type of tier (recurring or one-time).",
    )
    type = SelectField(
        "Type",
        choices=SubscriptionTierType.choices(),
        coerce=SubscriptionTierType.coerce,
        default=SubscriptionTierType.PRIMARY.value,
        validators=[validators.Optional()],
        description="Type of subscription (primary or add-on). Only applies to recurring mode.",
    )
    interval = SelectField(
        "Interval",
        choices=SubscriptionInterval.choices(),
        coerce=SubscriptionInterval.coerce,
        default=SubscriptionInterval.MONTH.value,
        validators=[validators.Optional()],
        description="Time unit for the billing interval (days, months, years) for recurring tiers.",
    )
    interval_count = IntegerField(
        "Interval Count",
        validators=[validators.Optional()],
        default=1,
        description="Number of intervals between billings for recurring tiers.",
    )
    quantity = IntegerField(
        "Quantity",
        validators=[validators.InputRequired()],
        default=1,
        description="Quantity for this tier (e.g., number of credits).",
    )
    stripe_price_id = StringField(
        "Stripe Price ID",
        validators=[validators.InputRequired()],
        description="The Stripe price ID for this tier.",
    )
    is_public = BooleanField("Public", default=True)


class OrganizationSubscriptionForm(CSRFBaseForm):
    organization = ComboboxSelectField(
        "Organization",
        query_endpoint_path="/admin/users/organizations/",
        validators=[validators.InputRequired(), validators.UUID()],
    )
    tier = ComboboxSelectField(
        "Subscription Tier",
        query_endpoint_path="/admin/subscriptions/tiers/",
        validators=[validators.Optional(), validators.UUID()],
    )
    roles = ComboboxSelectMultipleField(
        "Roles",
        query_endpoint_path="/admin/access-control/roles/",
        label_attr="display_name",
        validators=[validators.Optional()],
        description="Roles that will be granted to users with this subscription.",
    )
    accounts = IntegerField(
        "Accounts",
        validators=[validators.InputRequired()],
        default=1,
    )
    quantity = IntegerField(
        "Quantity",
        validators=[validators.InputRequired()],
        default=1,
    )
    interval = SelectField(
        "Interval",
        choices=SubscriptionInterval.choices(),
        coerce=SubscriptionInterval.coerce,
        default=SubscriptionInterval.MONTH.value,
        validators=[validators.Optional()],
    )
    interval_count = IntegerField(
        "Interval Count",
        validators=[validators.Optional()],
        default=1,
    )
    grace_period = IntegerField(
        "Grace Period (days)",
        validators=[validators.InputRequired()],
        default=7,
    )
    status = SelectField(
        "Status",
        choices=SubscriptionStatus.choices(),
        coerce=SubscriptionStatus.coerce,
        default=SubscriptionStatus.PENDING.value,
        validators=[validators.InputRequired()],
    )
    stripe_subscription_id = StringField(
        "Stripe Subscription ID",
        validators=[validators.InputRequired()],
    )
