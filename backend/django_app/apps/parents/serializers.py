from rest_framework import serializers

from apps.accounts.models import User
from apps.core.serializers import PublicIdRelatedField
from apps.students.models import Student

from .models import Guardian, GuardianStudent


class GuardianSerializer(serializers.ModelSerializer):
    # `User.objects` (the manager), not `.all()` — DRF's RelatedField
    # re-evaluates a bare manager's `.all()` lazily per-request, whereas a
    # pre-built queryset would freeze TenantManager's org-scoping at import
    # time (no request context yet), permanently baking in an empty set.
    user = PublicIdRelatedField(queryset=User.objects, required=False, allow_null=True)

    class Meta:
        model = Guardian
        fields = ["public_id", "user", "first_name", "last_name", "phone", "email", "occupation"]


class GuardianStudentSerializer(serializers.ModelSerializer):
    guardian = PublicIdRelatedField(queryset=Guardian.objects)
    student = PublicIdRelatedField(queryset=Student.objects)

    class Meta:
        model = GuardianStudent
        fields = ["public_id", "guardian", "student", "relationship_type", "is_primary"]
        # Both fields of the model's UniqueConstraint (guardian, student)
        # are serializer fields, so DRF would otherwise auto-add a
        # UniqueTogetherValidator — bypassing the envelope with a raw 400
        # instead of the clean 409 the EnvelopeCreateMixin IntegrityError
        # handler produces (see core/generics.py). Same convention as
        # apps.schools, which avoids this by keeping the constrained
        # `organization` field out of its serializers entirely.
        validators = []
