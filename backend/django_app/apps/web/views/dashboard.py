from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from apps.parents.models import Guardian
from apps.staff.models import Staff, Teacher
from apps.students.models import ENROLLMENT_STATUS_CHOICES, Student

from ..permissions import can


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
        can_view_students = can(user, "students.view")
        can_view_staff = can(user, "staff.view")
        can_view_teachers = can(user, "teachers.view")
        can_view_guardians = can(user, "guardians.view")
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
