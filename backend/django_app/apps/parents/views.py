"""Thin views, fat services (§11 ARCHITECTURE.md). Every list/detail view
here filters out soft-deleted rows locally (`deleted_at__isnull=True`) —
see apps/schools/views.py's identical note; not (yet) pushed into
TenantManager since no other app needs it.
"""
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView

from .models import Guardian, GuardianStudent
from .serializers import GuardianSerializer, GuardianStudentSerializer
from .services import guardian_service, guardian_student_service


class GuardianListCreateView(TenantListCreateAPIView):
    serializer_class = GuardianSerializer

    def get_queryset(self):
        return Guardian.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = "guardians.create" if self.request.method == "POST" else "guardians.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        serializer.instance = guardian_service.create_guardian(
            organization=self.request.user.organization, actor=self.request.user, **serializer.validated_data
        )


class GuardianDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = GuardianSerializer

    def get_queryset(self):
        return Guardian.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "guardians.view", "PATCH": "guardians.update", "DELETE": "guardians.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        guardian_service.update_guardian(
            guardian=serializer.instance, actor=self.request.user, **serializer.validated_data
        )

    def perform_destroy(self, instance):
        guardian_service.delete_guardian(guardian=instance, actor=self.request.user)


class GuardianStudentListCreateView(TenantListCreateAPIView):
    serializer_class = GuardianStudentSerializer

    def get_queryset(self):
        qs = GuardianStudent.objects.filter(deleted_at__isnull=True)
        guardian_id = self.request.query_params.get("guardian_id")
        if guardian_id:
            qs = qs.filter(guardian__public_id=guardian_id)
        student_id = self.request.query_params.get("student_id")
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        return qs

    def get_permissions(self):
        code = "guardian_students.create" if self.request.method == "POST" else "guardian_students.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        guardian = data.pop("guardian")
        student = data.pop("student")
        serializer.instance = guardian_student_service.link_guardian_student(
            guardian=guardian, student=student, actor=self.request.user, **data
        )


class GuardianStudentDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = GuardianStudentSerializer

    def get_queryset(self):
        return GuardianStudent.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "guardian_students.view",
            "PATCH": "guardian_students.update",
            "DELETE": "guardian_students.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("guardian", None)
        data.pop("student", None)
        guardian_student_service.update_guardian_student(
            link=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        guardian_student_service.unlink_guardian_student(link=instance, actor=self.request.user)
