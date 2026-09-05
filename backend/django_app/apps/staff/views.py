"""Thin views, fat services (§11 ARCHITECTURE.md). `school` on Staff and
`staff` on Teacher are write-required on create but stripped before
update — re-parenting would leave a denormalized `organization` stale
(see models.py), so that's a deliberate operation out of M4 scope, same
convention as apps.schools.views.
"""
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView
from apps.core.responses import envelope, error_envelope

from .models import Staff, Teacher
from .serializers import StaffSerializer, TeacherSerializer
from .services import bulk_import_service, staff_service, teacher_service


class StaffListCreateView(TenantListCreateAPIView):
    serializer_class = StaffSerializer

    def get_queryset(self):
        qs = Staff.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        department_id = self.request.query_params.get("department_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        if department_id:
            qs = qs.filter(department__public_id=department_id)
        return qs

    def get_permissions(self):
        code = "staff.create" if self.request.method == "POST" else "staff.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = staff_service.create_staff(school=school, actor=self.request.user, **data)


class StaffDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = StaffSerializer

    def get_queryset(self):
        return Staff.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "staff.view", "PATCH": "staff.update", "DELETE": "staff.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        staff_service.update_staff(staff=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        staff_service.delete_staff(staff=instance, actor=self.request.user)


class StaffBulkImportView(APIView):
    """A single CSV/XLSX upload creates many staff members in one request —
    see apps.staff.services.bulk_import_service for the row shape and
    per-row partial-success behavior."""

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, require_permission("staff.create")]

    def post(self, request):
        file_obj = request.FILES.get("file")
        if file_obj is None:
            return error_envelope("a file is required", status=400)
        if not file_obj.name.lower().endswith((".csv", ".xlsx")):
            return error_envelope("only .csv and .xlsx files are supported", status=400)

        rows = bulk_import_service.parse_rows(filename=file_obj.name, content=file_obj.read())
        if not rows:
            return error_envelope("the file has no data rows", status=400)

        result = bulk_import_service.import_staff(
            organization=request.user.organization, actor=request.user, rows=rows
        )
        return envelope(result, message=f"{result['created']} of {len(rows)} row(s) imported")


class TeacherListCreateView(TenantListCreateAPIView):
    serializer_class = TeacherSerializer

    def get_queryset(self):
        qs = Teacher.objects.filter(deleted_at__isnull=True)
        staff_id = self.request.query_params.get("staff_id")
        if staff_id:
            qs = qs.filter(staff__public_id=staff_id)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(staff__school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "teachers.create" if self.request.method == "POST" else "teachers.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        staff = data.pop("staff")
        serializer.instance = teacher_service.create_teacher_profile(
            staff=staff, actor=self.request.user, **data
        )


class TeacherDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = TeacherSerializer

    def get_queryset(self):
        return Teacher.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "teachers.view", "PATCH": "teachers.update", "DELETE": "teachers.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("staff", None)
        teacher_service.update_teacher_profile(teacher=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        teacher_service.delete_teacher_profile(teacher=instance, actor=self.request.user)
