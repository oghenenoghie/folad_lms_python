"""Thin views, fat services (§11 ARCHITECTURE.md) — same convention as
every API app. The one new piece of logic here (§5 UI_MIGRATION_PLAN.md)
is establishing a Django session after `auth_service.login()` validates
credentials/MFA/lockout; nothing about that validation is reimplemented.
"""
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView

from apps.accounts.models import User
from apps.accounts.permissions import get_user_permission_codes
from apps.accounts.services import auth_service
from apps.parents.models import Guardian
from apps.staff.models import Staff, Teacher
from apps.students.models import ENROLLMENT_STATUS_CHOICES, Student

from .forms import WebLoginForm


def _can(user, code: str) -> bool:
    """Same rule apps.accounts.permissions.HasPermission enforces on the
    JSON API (superuser bypass, else a real granted permission code) —
    reused here, not reimplemented, so a server-rendered page can never
    show a section the API itself would reject."""
    return bool(user.is_superuser or code in get_user_permission_codes(user))


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


class HomeView(LoginRequiredMixin, TemplateView):
    """Permission-driven per UI_MIGRATION_PLAN.md §7a: no seeded system
    roles exist (Role starts empty — see the plan), so visibility is keyed
    off the permission codes the signed-in user actually holds, exactly
    like the JSON API's own `require_permission()` checks. A user with no
    granted permissions and no superuser flag sees an explicit empty
    state, never a silently-blank dashboard."""

    login_url = reverse_lazy("web:login")
    template_name = "web/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumb_items"] = [("Dashboard", None)]

        user = self.request.user
        can_view_students = _can(user, "students.view")
        can_view_staff = _can(user, "staff.view")
        can_view_teachers = _can(user, "teachers.view")
        can_view_guardians = _can(user, "guardians.view")
        context["can_view_students"] = can_view_students
        context["can_view_staff"] = can_view_staff
        context["can_view_teachers"] = can_view_teachers
        context["can_view_guardians"] = can_view_guardians
        context["has_any_dashboard_access"] = any(
            [can_view_students, can_view_staff, can_view_teachers, can_view_guardians]
        )

        # TenantManager (apps.web.middleware.WebTenantContextMiddleware
        # having activated this request's org above) — real counts for the
        # signed-in user's own organization, nothing fabricated. A
        # platform-level account (organization=None) correctly sees zeros:
        # TenantManager fails closed with no organization in context.
        if can_view_students:
            students = Student.objects.filter(deleted_at__isnull=True)
            context["student_count"] = students.count()
            context["recent_students"] = students.order_by("-created_at")[:5]
            # Real distribution, not a fabricated chart — empty dict (and
            # the "no data yet" empty state) when there's nothing to plot.
            status_labels = dict(ENROLLMENT_STATUS_CHOICES)
            counts = dict(
                students.values_list("enrollment_status").annotate(n=Count("id")).order_by()
            )
            context["enrollment_breakdown"] = {
                status_labels.get(status, status): count for status, count in counts.items()
            }
        if can_view_staff:
            context["staff_count"] = Staff.objects.filter(deleted_at__isnull=True).count()
        if can_view_teachers:
            context["teacher_count"] = Teacher.objects.filter(deleted_at__isnull=True).count()
        if can_view_guardians:
            context["guardian_count"] = Guardian.objects.filter(deleted_at__isnull=True).count()
        return context
