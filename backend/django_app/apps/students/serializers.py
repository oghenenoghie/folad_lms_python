from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField
from apps.parents.models import Guardian
from apps.schools.models import School

from .models import GuardianStudent, Student


class StudentSerializer(serializers.ModelSerializer):
    # `School.objects` (the manager), not `.all()` — DRF's RelatedField
    # re-evaluates a bare manager's `.all()` lazily per-request, whereas a
    # pre-built queryset would freeze TenantManager's org-scoping at import
    # time (no request context yet), permanently baking in an empty set.
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = Student
        fields = [
            "public_id",
            "school",
            "admission_number",
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "enrollment_status",
        ]
        # See the note in apps.staff.serializers.StaffSerializer.Meta: both
        # fields of uq_student_school_admission_number are serializer
        # fields, so DRF would otherwise auto-add a UniqueTogetherValidator
        # that bypasses the envelope with a raw 400.
        validators = []


class GuardianStudentSerializer(serializers.ModelSerializer):
    student = PublicIdRelatedField(queryset=Student.objects)
    guardian = PublicIdRelatedField(queryset=Guardian.objects)

    class Meta:
        model = GuardianStudent
        fields = ["public_id", "student", "guardian", "relationship_type", "is_primary"]
        # See the note in apps.staff.serializers.StaffSerializer.Meta.
        validators = []
