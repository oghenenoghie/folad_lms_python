from django import forms

_INPUT_ATTRS = {"class": "field-input"}


class WebLoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={**_INPUT_ATTRS, "autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs=_INPUT_ATTRS))
    totp_code = forms.CharField(
        required=False,
        label="Authenticator code",
        widget=forms.TextInput(attrs={**_INPUT_ATTRS, "autocomplete": "one-time-code"}),
    )


class MFAVerifyForm(forms.Form):
    code = forms.CharField(
        label="Authenticator code",
        widget=forms.TextInput(
            attrs={**_INPUT_ATTRS, "autocomplete": "one-time-code", "autofocus": True, "maxlength": 6}
        ),
    )
