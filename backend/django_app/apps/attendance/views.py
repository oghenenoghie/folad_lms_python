"""Thin views, fat services (§11 ARCHITECTURE.md). `enrollment` is
write-required on create but stripped before update — re-parenting a
record to a different enrollment would leave its denormalized
`organization` stale (see models.py), same convention as every other
app. AttendanceAudit has no create/update/delete view at all: it's
written only by attendance_service alongside an Attendance write, and
the database trigger from apps.tenancy.db.make_append_only rejects any
attempt to mutate it directly regardless.
"""
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import require_permission
from apps.core.generics import (
    TenantListAPIView,
    TenantListCreateAPIView,
    TenantRetrieveUpdateDestroyAPIView,
)

from .models import Attendance, AttendanceAudit
from .serializers import AttendanceAuditSerializer, AttendanceSerializer
from .services import attendance_service


class AttendanceListCreateView(TenantListCreateAPIView):
    serializer_class = AttendanceSerializer

    def get_queryset(self):
        qs = Attendance.objects.filter(deleted_at__isnull=True)
        enrollment_id = self.request.query_params.get("enrollment_id")
        date = self.request.query_params.get("date")
        if enrollment_id:
            qs = qs.filter(enrollment__public_id=enrollment_id)
        if date:
            qs = qs.filter(date=date)
        return qs

    def get_permissions(self):
        code = "attendance.create" if self.request.method == "POST" else "attendance.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        enrollment = data.pop("enrollment")
        serializer.instance = attendance_service.mark_attendance(
            enrollment=enrollment, actor=self.request.user, **data
        )


class AttendanceDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = AttendanceSerializer

    def get_queryset(self):
        return Attendance.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "attendance.view",
            "PATCH": "attendance.update",
            "DELETE": "attendance.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("enrollment", None)
        attendance_service.update_attendance(
            attendance=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        attendance_service.delete_attendance(attendance=instance, actor=self.request.user)


class AttendanceAuditListView(TenantListAPIView):
    serializer_class = AttendanceAuditSerializer

    def get_queryset(self):
        qs = AttendanceAudit.objects.select_related("changed_by")
        attendance_id = self.request.query_params.get("attendance_id")
        if attendance_id:
            qs = qs.filter(attendance__public_id=attendance_id)
        return qs

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("attendance.view")()]
