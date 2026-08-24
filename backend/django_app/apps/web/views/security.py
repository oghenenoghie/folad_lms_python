from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.services import mfa_service

from ..forms.security import MFAVerifyForm


def _security_context(request, verify_form=None):
    user = request.user
    context = {
        "breadcrumb_items": [("Dashboard", reverse_lazy("web:home")), ("Security", None)],
        "mfa_enabled": user.mfa_enabled,
        "mfa_pending": bool(user.mfa_secret and not user.mfa_enabled),
        "verify_form": verify_form or MFAVerifyForm(),
    }
    if context["mfa_pending"]:
        context["mfa_secret"] = user.mfa_secret
        context["mfa_otpauth_uri"] = mfa_service.provisioning_uri_for(user)
    return context


class SecurityView(LoginRequiredMixin, TemplateView):
    """Self-service MFA enrollment (§5 UI_MIGRATION_PLAN.md's Phase 5) —
    wraps apps.accounts.services.mfa_service, the same module the JSON
    API's MFAEnrollView/MFAVerifyView call, so enabling MFA here has
    identical effect to enabling it through the API."""

    login_url = reverse_lazy("web:login")
    template_name = "web/security.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_security_context(self.request))
        return context


class MFAEnrollStartView(LoginRequiredMixin, View):
    login_url = reverse_lazy("web:login")

    def post(self, request, *args, **kwargs):
        mfa_service.start_enrollment(request.user)
        return redirect("web:security")


class MFAVerifySubmitView(LoginRequiredMixin, View):
    login_url = reverse_lazy("web:login")
    template_name = "web/security.html"

    def post(self, request, *args, **kwargs):
        form = MFAVerifyForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, _security_context(request, verify_form=form))

        try:
            mfa_service.confirm_enrollment(user=request.user, code=form.cleaned_data["code"])
        except mfa_service.MFANotInProgressError:
            messages.error(request, "Start enrollment again before verifying a code.")
            return redirect("web:security")
        except mfa_service.MFAInvalidCodeError:
            form.add_error("code", "That code isn't valid. Check the time on your device and try again.")
            return render(request, self.template_name, _security_context(request, verify_form=form))

        messages.success(request, "Two-factor authentication is now enabled on your account.")
        return redirect("web:security")
