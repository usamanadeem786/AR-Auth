from wtforms import HiddenField

from auth.forms import CSRFBaseForm


class AcceptInvitationForm(CSRFBaseForm):
    token = HiddenField()
