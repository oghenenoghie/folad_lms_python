"""Thin views, fat services (§11 ARCHITECTURE.md). `school` on Student is
write-required on create but stripped before update — re-parenting a
student to a different school would leave its denormalized `organization`
stale (see models.py), so a transfer is a deliberate operation out of M4
scope, same convention as apps.schools.views.
"""
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView

from .models import Student
from .serializers import StudentSerializer
from .services import student_service


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
