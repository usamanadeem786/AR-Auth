from wtforms import BooleanField, StringField, validators

from auth.forms import CSRFBaseForm


class PermissionCreateForm(CSRFBaseForm):
    name = StringField(
        "Name",
        validators=[validators.InputRequired()],
        render_kw={"placeholder": "Create Castle"},
    )
    codename = StringField(
        "Codename",
        validators=[validators.InputRequired()],
        render_kw={"placeholder": "castles:create"},
    )

    is_public = BooleanField(
        "Public",
        default=True,
        # description="Whether this permission is publicly available.",
    )
