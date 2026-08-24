from rest_framework import serializers

from apps.accounts.models import User
from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import School

from .models import Student


class StudentSerializer(serializers.ModelSerializer):
    # `School.objects`/`User.objects` (the manager), not `.all()` — DRF's
    # RelatedField re-evaluates a bare manager's `.all()` lazily per-request,
    # whereas a pre-built queryset would freeze TenantManager's org-scoping
    # at import time (no request context yet), permanently baking in an
    # empty set.
    school = PublicIdRelatedField(queryset=School.objects)
    user = PublicIdRelatedField(queryset=User.objects, required=False, allow_null=True)

    class Meta:
        model = Student
        fields = [
            "public_id",
            "school",
            "user",
            "admission_number",
            "first_name",
            "last_name",
            "date_of_birth",
            "enrollment_status",
        ]
