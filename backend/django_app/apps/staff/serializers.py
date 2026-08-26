from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import Department, School

from .models import Staff, Teacher


class StaffSerializer(serializers.ModelSerializer):
    # `School.objects`/`Department.objects` (the manager), not `.all()` —
    # DRF's RelatedField re-evaluates a bare manager's `.all()` lazily
    # per-request, whereas a pre-built queryset would freeze TenantManager's
    # org-scoping at import time (no request context yet), permanently
    # baking in an empty set.
    school = PublicIdRelatedField(queryset=School.objects)
    department = PublicIdRelatedField(queryset=Department.objects, required=False, allow_null=True)

    class Meta:
        model = Staff
        fields = [
            "public_id",
            "school",
            "department",
            "staff_number",
            "first_name",
            "last_name",
            "phone",
            "email",
            "employment_status",
            "hire_date",
        ]
        # Both fields of the model's UniqueConstraint (school, staff_number)
        # are serializer fields, so DRF would otherwise auto-add a
        # UniqueTogetherValidator — bypassing the envelope with a raw 400
        # instead of the clean 409 the EnvelopeCreateMixin IntegrityError
        # handler produces (see core/generics.py). Same convention as
        # apps.schools, which avoids this by keeping the constrained
        # `organization` field out of its serializers entirely.
        validators = []


class TeacherSerializer(serializers.ModelSerializer):
    staff = PublicIdRelatedField(queryset=Staff.objects)

    class Meta:
        model = Teacher
        fields = ["public_id", "staff", "qualification", "specialization", "is_active"]
