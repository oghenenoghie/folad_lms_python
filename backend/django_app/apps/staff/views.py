"""Thin views, fat services (§11 ARCHITECTURE.md). Every list/detail view
here filters out soft-deleted rows locally (`deleted_at__isnull=True`) —
see apps/schools/views.py's identical note; not (yet) pushed into
TenantManager since no other app needs it.
"""
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView

from .models import Staff, Teacher
from .serializers import StaffSerializer, TeacherSerializer
from .services import staff_service, teacher_service


class StaffListCreateView(TenantListCreateAPIView):
    serializer_class = StaffSerializer

    def get_queryset(self):
        qs = Staff.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        department_id = self.request.query_params.get("department_id")
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


class TeacherListCreateView(TenantListCreateAPIView):
    serializer_class = TeacherSerializer

    def get_queryset(self):
        qs = Teacher.objects.filter(deleted_at__isnull=True)
        staff_id = self.request.query_params.get("staff_id")
        if staff_id:
            qs = qs.filter(staff__public_id=staff_id)
        return qs

    def get_permissions(self):
        code = "teachers.create" if self.request.method == "POST" else "teachers.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        staff = data.pop("staff")
        serializer.instance = teacher_service.create_teacher(staff=staff, actor=self.request.user, **data)


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
        teacher_service.update_teacher(teacher=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        teacher_service.delete_teacher(teacher=instance, actor=self.request.user)
