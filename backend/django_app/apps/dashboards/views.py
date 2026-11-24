"""Thin views, fat services (§11 ARCHITECTURE.md). No RBAC permission beyond
IsAuthenticated — every view here is always the requesting user's own role-
appropriate view, never another user's or the whole organization's raw
data, same self-scoping rationale as apps.communication's Notification/
Message endpoints. The generic *.view RBAC permissions (e.g.
"attendance.view") are deliberately never reused here: those are org-wide
(any holder sees every student's records), so a Student/Guardian role must
never be granted them — this is the safe, scoped alternative.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.assignments.models import Assignment
from apps.assignments.serializers import AssignmentSerializer
from apps.attendance.models import Attendance
from apps.attendance.serializers import AttendanceSerializer
from apps.core.generics import TenantListAPIView
from apps.core.responses import envelope, error_envelope
from apps.examinations.models import Result
from apps.examinations.serializers import ResultSerializer
from apps.finance.models import Invoice
from apps.finance.serializers import InvoiceSerializer
from apps.parents.models import GuardianStudent
from apps.students.models import Student
from apps.students.serializers import StudentSerializer

from .services import dashboard_service


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return envelope(dashboard_service.get_summary(user=request.user))


def _resolve_target_student(request):
    """Which Student's records `request.user` may see through the my-*
    endpoints below: a student always sees their own; a guardian must name
    one of their own linked children via `?student_id=<public_id>`; anyone
    else (staff/admin) isn't a self-service user at all and should use the
    regular, permission-gated CRUD endpoints instead.

    Returns (student, error_response) — exactly one is None.
    """
    student = getattr(request.user, "student_profile", None)
    if student is not None:
        return student, None

    guardian = getattr(request.user, "guardian_profile", None)
    if guardian is not None:
        student_id = request.query_params.get("student_id")
        if not student_id:
            return None, error_envelope("student_id is required", status=400)
        link = (
            GuardianStudent.objects.filter(
                guardian=guardian, student__public_id=student_id, deleted_at__isnull=True
            )
            .select_related("student")
            .first()
        )
        if link is None:
            return None, error_envelope("student not found", status=404)
        return link.student, None

    return None, error_envelope("this endpoint is only available to students and guardians", status=403)


class StudentScopedListMixin:
    """Resolves the target student before every list() call and stashes it
    on `self._target_student` for get_queryset() to filter by — see
    _resolve_target_student() above for who that student is allowed to be.
    """

    def get_permissions(self):
        return [IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        student, error = _resolve_target_student(request)
        if error is not None:
            return error
        self._target_student = student
        return super().list(request, *args, **kwargs)


class MyChildrenView(TenantListAPIView):
    """A guardian's own linked children — lets a guardian discover the
    student_id values to pass into the other my-* endpoints below. Not
    meaningful for a student (they have no children), so it's simply empty
    for anyone else.
    """

    serializer_class = StudentSerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        guardian = getattr(self.request.user, "guardian_profile", None)
        if guardian is None:
            return Student.objects.none()
        return Student.objects.filter(
            guardian_links__guardian=guardian, deleted_at__isnull=True
        ).distinct()


class MyAssignmentsView(StudentScopedListMixin, TenantListAPIView):
    serializer_class = AssignmentSerializer

    def get_queryset(self):
        return Assignment.objects.filter(
            class_subject__class_arm__enrollments__student=self._target_student,
            class_subject__class_arm__enrollments__status="active",
        ).distinct()


class MyAttendanceView(StudentScopedListMixin, TenantListAPIView):
    serializer_class = AttendanceSerializer

    def get_queryset(self):
        qs = Attendance.objects.filter(enrollment__student=self._target_student)
        date = self.request.query_params.get("date")
        if date:
            qs = qs.filter(date=date)
        return qs


class MyResultsView(StudentScopedListMixin, TenantListAPIView):
    serializer_class = ResultSerializer

    def get_queryset(self):
        # Only the published, final view — "entered"/other in-progress
        # workflow states (see apps.examinations) are an internal
        # teacher/admin concern, never exposed to the student or guardian
        # who owns the record.
        return Result.objects.filter(student=self._target_student, status="published")


class MyInvoicesView(StudentScopedListMixin, TenantListAPIView):
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        return Invoice.objects.filter(student=self._target_student)
