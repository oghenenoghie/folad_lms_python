from django import forms

from .base import StyledForm


class MFAVerifyForm(StyledForm):
    code = forms.CharField(
        label="Authenticator code",
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "autofocus": True, "maxlength": 6}),
    )
