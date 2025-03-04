from wtforms import (BooleanField, IntegerField, SelectField, StringField,
                     TextAreaField, validators)

from auth.forms import (ComboboxSelectField, ComboboxSelectMultipleField,
                        CSRFBaseForm, empty_string_to_none)
from auth.models.subscription_plan import SubscriptionPlanExpiryUnit


class BaseSubscriptionPlanForm(CSRFBaseForm):
    name = StringField("Name", validators=[validators.InputRequired()])
    details = TextAreaField(
        "Details",
        validators=[validators.Optional()],
        filters=[empty_string_to_none],
        description="Description of the subscription plan.",
    )
    granted_by_default = BooleanField("Grant by default", default=False)
    expiry_interval = IntegerField(
        "Expiry interval",
        validators=[validators.InputRequired()],
        default=1,
        description="Number of time units until the subscription expires.",
    )
    expiry_unit = SelectField(
        "Expiry unit",
        choices=SubscriptionPlanExpiryUnit.choices(),
        coerce=SubscriptionPlanExpiryUnit.coerce,
        default=SubscriptionPlanExpiryUnit.MONTH.value,
        validators=[validators.InputRequired()],
        description="Time unit for the expiry interval (days, months, years).",
    )

    roles = ComboboxSelectMultipleField(
        "Roles",
        query_endpoint_path="/admin/access-control/roles/",
        label_attr="display_name",
        choices=[],
        validators=[validators.InputRequired()],
        validate_choice=False,
        description="Roles that will be granted to users with this subscription plan.",
    )


class SubscriptionPlanCreateForm(BaseSubscriptionPlanForm):
    tenant = ComboboxSelectField(
        "Tenant",
        query_endpoint_path="/admin/tenants/",
        validators=[validators.InputRequired(), validators.UUID()],
    )


class SubscriptionPlanUpdateForm(BaseSubscriptionPlanForm):
    pass


class UserSubscriptionForm(CSRFBaseForm):
    subscription_plan = ComboboxSelectMultipleField(
        "Subscription Plan",
        query_endpoint_path="/admin/subscription-plans/",
        label_attr="name",
        choices=[],
        validate_choice=False,
    )
