"""Thin views, fat services (§11 ARCHITECTURE.md). `school` on Student is
write-required on create but stripped before update — re-parenting a
student to a different school would leave its denormalized `organization`
stale (see models.py), so a transfer is a deliberate operation out of M4
scope, same convention as apps.schools.views.
"""
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView
from apps.core.responses import envelope, error_envelope

from .models import Student
from .serializers import StudentSerializer
from .services import bulk_import_service, student_service


class StudentListCreateView(TenantListCreateAPIView):
    serializer_class = StudentSerializer

    def get_queryset(self):
        qs = Student.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "students.create" if self.request.method == "POST" else "students.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = student_service.create_student(school=school, actor=self.request.user, **data)


class StudentDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = StudentSerializer

    def get_queryset(self):
        return Student.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "students.view", "PATCH": "students.update", "DELETE": "students.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        student_service.update_student(student=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        student_service.delete_student(student=instance, actor=self.request.user)


class StudentBulkImportView(APIView):
    """A single CSV/XLSX upload creates many students in one request — see
    apps.students.services.bulk_import_service for the row shape and
    per-row partial-success behavior. Gated on the same permission as a
    single create, since this is just many creates in one call.
    """

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, require_permission("students.create")]

    def post(self, request):
        file_obj = request.FILES.get("file")
        if file_obj is None:
            return error_envelope("a file is required", status=400)
        if not file_obj.name.lower().endswith((".csv", ".xlsx")):
            return error_envelope("only .csv and .xlsx files are supported", status=400)

        rows = bulk_import_service.parse_rows(filename=file_obj.name, content=file_obj.read())
        if not rows:
            return error_envelope("the file has no data rows", status=400)

        result = bulk_import_service.import_students(
            organization=request.user.organization, actor=request.user, rows=rows
        )
        return envelope(result, message=f"{result['created']} of {len(rows)} row(s) imported")
