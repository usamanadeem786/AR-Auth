from wtforms import PasswordField, validators

from auth.forms import CSRFBaseForm, PasswordValidator
from auth.locale import gettext_lazy as _


class ChangePasswordForm(CSRFBaseForm):
    old_password = PasswordField(
        _("Old password"),
        validators=[validators.InputRequired()],
        render_kw={"autocomplete": "current-password"},
    )
    new_password = PasswordField(
        _("New password"),
        validators=[validators.InputRequired(), PasswordValidator()],
        render_kw={"autocomplete": "new-password"},
    )
    new_password_confirm = PasswordField(
        _("Confirm new password"),
        validators=[validators.InputRequired()],
        render_kw={"autocomplete": "new-password"},
    )
