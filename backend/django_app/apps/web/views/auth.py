"""Thin views, fat services (§11 ARCHITECTURE.md). The one new piece of
logic here (§5 UI_MIGRATION_PLAN.md) is establishing a Django session
after `auth_service.login()` validates credentials/MFA/lockout; nothing
about that validation is reimplemented.
"""
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView

from apps.accounts.models import User
from apps.accounts.services import auth_service

from ..forms.auth import WebLoginForm


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class WebLoginView(FormView):
    template_name = "web/login.html"
    form_class = WebLoginForm
    success_url = reverse_lazy("web:home")

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            auth_service.login(
                email=data["email"],
                password=data["password"],
                totp_code=data.get("totp_code") or None,
                ip_address=_client_ip(self.request),
                user_agent=self.request.META.get("HTTP_USER_AGENT", ""),
            )
        except auth_service.MFARequiredError:
            form.add_error("totp_code", "An authenticator code is required for this account.")
            return self.form_invalid(form)
        except auth_service.MFAInvalidError:
            form.add_error("totp_code", "That authenticator code isn't valid.")
            return self.form_invalid(form)
        except (auth_service.AccountLockedError, auth_service.InvalidCredentialsError) as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        # auth_service.login() just validated these exact credentials — this
        # re-fetch only recovers the User object it doesn't return (it
        # returns a JWT TokenPair, for the JSON API's callers), never a
        # second credential check.
        user = User.all_tenants.get(email__iexact=data["email"])
        django_login(self.request, user, backend="apps.accounts.backends.TenantAwareModelBackend")
        return super().form_valid(form)


class WebLogoutView(LoginRequiredMixin, View):
    login_url = reverse_lazy("web:login")

    def post(self, request, *args, **kwargs):
        django_logout(request)
        return redirect("web:login")
