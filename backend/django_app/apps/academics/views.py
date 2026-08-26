"""Thin views, fat services (§11 ARCHITECTURE.md). Parent-FK fields are
write-required on create but stripped before update — re-parenting a
resource to a different parent would leave its denormalized
`organization` stale (see models.py), so that's a deliberate operation
out of M5 scope, same convention as apps.schools/apps.staff/apps.students.
Enrollment is the one exception: `class_arm` (a same-tenant transfer) and
`academic_year` stay updatable, since neither touches `organization` and
a mid-year class-arm transfer is exactly the kind of update this model
exists to support — only `student` is immutable.
"""
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView

from .models import ClassArm, ClassLevel, ClassSubject, Enrollment, Subject
from .serializers import (
    ClassArmSerializer,
    ClassLevelSerializer,
    ClassSubjectSerializer,
    EnrollmentSerializer,
    SubjectSerializer,
)
from .services import (
    class_arm_service,
    class_level_service,
    class_subject_service,
    enrollment_service,
    subject_service,
)


class ClassLevelListCreateView(TenantListCreateAPIView):
    serializer_class = ClassLevelSerializer

    def get_queryset(self):
        qs = ClassLevel.objects.filter(deleted_at__isnull=True)
        campus_id = self.request.query_params.get("campus_id")
        if campus_id:
            qs = qs.filter(campus__public_id=campus_id)
        return qs

    def get_permissions(self):
        code = "class_levels.create" if self.request.method == "POST" else "class_levels.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        campus = data.pop("campus")
        serializer.instance = class_level_service.create_class_level(
            campus=campus, actor=self.request.user, **data
        )


class ClassLevelDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = ClassLevelSerializer

    def get_queryset(self):
        return ClassLevel.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "class_levels.view",
            "PATCH": "class_levels.update",
            "DELETE": "class_levels.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("campus", None)
        class_level_service.update_class_level(
            class_level=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        class_level_service.delete_class_level(class_level=instance, actor=self.request.user)


class ClassArmListCreateView(TenantListCreateAPIView):
    serializer_class = ClassArmSerializer

    def get_queryset(self):
        qs = ClassArm.objects.filter(deleted_at__isnull=True)
        class_level_id = self.request.query_params.get("class_level_id")
        if class_level_id:
            qs = qs.filter(class_level__public_id=class_level_id)
        return qs

    def get_permissions(self):
        code = "class_arms.create" if self.request.method == "POST" else "class_arms.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        class_level = data.pop("class_level")
        serializer.instance = class_arm_service.create_class_arm(
            class_level=class_level, actor=self.request.user, **data
        )


class ClassArmDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = ClassArmSerializer

    def get_queryset(self):
        return ClassArm.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "class_arms.view", "PATCH": "class_arms.update", "DELETE": "class_arms.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("class_level", None)
        class_arm_service.update_class_arm(class_arm=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        class_arm_service.delete_class_arm(class_arm=instance, actor=self.request.user)


class SubjectListCreateView(TenantListCreateAPIView):
    serializer_class = SubjectSerializer

    def get_queryset(self):
        qs = Subject.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "subjects.create" if self.request.method == "POST" else "subjects.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = subject_service.create_subject(school=school, actor=self.request.user, **data)


class SubjectDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = SubjectSerializer

    def get_queryset(self):
        return Subject.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "subjects.view", "PATCH": "subjects.update", "DELETE": "subjects.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        subject_service.update_subject(subject=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        subject_service.delete_subject(subject=instance, actor=self.request.user)


class ClassSubjectListCreateView(TenantListCreateAPIView):
    serializer_class = ClassSubjectSerializer

    def get_queryset(self):
        qs = ClassSubject.objects.filter(deleted_at__isnull=True)
        class_arm_id = self.request.query_params.get("class_arm_id")
        subject_id = self.request.query_params.get("subject_id")
        teacher_id = self.request.query_params.get("teacher_id")
        if class_arm_id:
            qs = qs.filter(class_arm__public_id=class_arm_id)
        if subject_id:
            qs = qs.filter(subject__public_id=subject_id)
        if teacher_id:
            qs = qs.filter(teacher__public_id=teacher_id)
        return qs

    def get_permissions(self):
        code = "class_subjects.create" if self.request.method == "POST" else "class_subjects.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        class_arm = data.pop("class_arm")
        subject = data.pop("subject")
        teacher = data.pop("teacher")
        serializer.instance = class_subject_service.create_class_subject(
            class_arm=class_arm, subject=subject, teacher=teacher, actor=self.request.user, **data
        )


class ClassSubjectDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = ClassSubjectSerializer

    def get_queryset(self):
        return ClassSubject.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "class_subjects.view",
            "PATCH": "class_subjects.update",
            "DELETE": "class_subjects.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("class_arm", None)
        data.pop("subject", None)
        class_subject_service.update_class_subject(
            class_subject=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        class_subject_service.delete_class_subject(class_subject=instance, actor=self.request.user)


class EnrollmentListCreateView(TenantListCreateAPIView):
    serializer_class = EnrollmentSerializer

    def get_queryset(self):
        qs = Enrollment.objects.filter(deleted_at__isnull=True)
        student_id = self.request.query_params.get("student_id")
        class_arm_id = self.request.query_params.get("class_arm_id")
        academic_year_id = self.request.query_params.get("academic_year_id")
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        if class_arm_id:
            qs = qs.filter(class_arm__public_id=class_arm_id)
        if academic_year_id:
            qs = qs.filter(academic_year__public_id=academic_year_id)
        return qs

    def get_permissions(self):
        code = "enrollments.create" if self.request.method == "POST" else "enrollments.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        student = data.pop("student")
        class_arm = data.pop("class_arm")
        academic_year = data.pop("academic_year")
        serializer.instance = enrollment_service.create_enrollment(
            student=student,
            class_arm=class_arm,
            academic_year=academic_year,
            actor=self.request.user,
            **data,
        )


class EnrollmentDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = EnrollmentSerializer

    def get_queryset(self):
        return Enrollment.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "enrollments.view",
            "PATCH": "enrollments.update",
            "DELETE": "enrollments.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("student", None)
        enrollment_service.update_enrollment(enrollment=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        enrollment_service.delete_enrollment(enrollment=instance, actor=self.request.user)
