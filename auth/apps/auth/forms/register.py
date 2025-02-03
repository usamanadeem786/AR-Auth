from typing import TypeVar

from fastapi import Depends
from wtforms import EmailField, FormField, validators

from auth.dependencies.register import get_optional_registration_session
from auth.dependencies.user_field import get_registration_user_fields
from auth.forms import BaseForm, CSRFBaseForm, PasswordCreateFieldForm, get_form_field
from auth.locale import gettext_lazy as _
from auth.models import RegistrationSession, RegistrationSessionFlow, UserField


class RegisterFormBase(CSRFBaseForm):
    email = EmailField(
        _("Email address"), validators=[validators.InputRequired(), validators.Email()]
    )
    fields: FormField


RF = TypeVar("RF", bound=RegisterFormBase)


async def get_register_form_class(
    registration_user_fields: list[UserField] = Depends(get_registration_user_fields),
    registration_session: RegistrationSession | None = Depends(
        get_optional_registration_session
    ),
) -> type[RF]:
    class RegisterFormFields(BaseForm):
        pass

    for field in registration_user_fields:
        setattr(RegisterFormFields, field.slug, get_form_field(field))

    class RegisterForm(RegisterFormBase):
        fields = FormField(RegisterFormFields, separator=".")

    class RegisterPasswordForm(RegisterForm, PasswordCreateFieldForm):
        pass

    if registration_session is None or (
        registration_session is not None
        and registration_session.flow == RegistrationSessionFlow.PASSWORD
    ):
        return RegisterPasswordForm

    return RegisterForm
