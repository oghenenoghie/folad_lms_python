from django import forms

from .base import StyledForm


class WebLoginForm(StyledForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput)
    totp_code = forms.CharField(
        required=False,
        label="Authenticator code",
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code"}),
    )
