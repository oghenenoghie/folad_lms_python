from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import AcademicYear, Campus, School
from apps.staff.models import Teacher
from apps.students.models import Student

from .models import ClassArm, ClassLevel, ClassSubject, Enrollment, Subject


class ClassLevelSerializer(serializers.ModelSerializer):
    # `Campus.objects` (the manager), not `.all()` — DRF's RelatedField
    # re-evaluates a bare manager's `.all()` lazily per-request, whereas a
    # pre-built queryset would freeze TenantManager's org-scoping at import
    # time (no request context yet), permanently baking in an empty set.
    campus = PublicIdRelatedField(queryset=Campus.objects)

    class Meta:
        model = ClassLevel
        fields = ["public_id", "campus", "name", "sequence", "is_active"]
        # Both fields of uq_class_level_campus_name are serializer fields,
        # so DRF would otherwise auto-add a UniqueTogetherValidator —
        # bypassing the envelope with a raw 400 instead of the clean 409
        # the EnvelopeCreateMixin IntegrityError handler produces (see
        # core/generics.py).
        validators = []


class ClassArmSerializer(serializers.ModelSerializer):
    class_level = PublicIdRelatedField(queryset=ClassLevel.objects)

    class Meta:
        model = ClassArm
        fields = ["public_id", "class_level", "name", "is_active"]
        validators = []


class SubjectSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = Subject
        fields = ["public_id", "school", "name", "code", "is_active"]
        validators = []


class ClassSubjectSerializer(serializers.ModelSerializer):
    class_arm = PublicIdRelatedField(queryset=ClassArm.objects)
    subject = PublicIdRelatedField(queryset=Subject.objects)
    teacher = PublicIdRelatedField(queryset=Teacher.objects)

    class Meta:
        model = ClassSubject
        fields = ["public_id", "class_arm", "subject", "teacher", "is_active"]
        validators = []


class EnrollmentSerializer(serializers.ModelSerializer):
    student = PublicIdRelatedField(queryset=Student.objects)
    class_arm = PublicIdRelatedField(queryset=ClassArm.objects)
    academic_year = PublicIdRelatedField(queryset=AcademicYear.objects)

    class Meta:
        model = Enrollment
        fields = [
            "public_id",
            "student",
            "class_arm",
            "academic_year",
            "status",
            "effective_from",
            "effective_to",
        ]
        validators = []
