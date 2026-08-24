from rest_framework import serializers

from apps.accounts.models import User
from apps.core.serializers import PublicIdRelatedField
from apps.students.models import Student

from .models import Guardian, GuardianStudent


class GuardianSerializer(serializers.ModelSerializer):
    # `User.objects` (the manager), not `.all()` — see students/serializers.py.
    user = PublicIdRelatedField(queryset=User.objects, required=False, allow_null=True)

    class Meta:
        model = Guardian
        fields = ["public_id", "user", "first_name", "last_name", "phone", "email", "occupation"]


class GuardianStudentSerializer(serializers.ModelSerializer):
    guardian = PublicIdRelatedField(queryset=Guardian.objects)
    student = PublicIdRelatedField(queryset=Student.objects)

    class Meta:
        model = GuardianStudent
        fields = ["public_id", "guardian", "student", "relationship_type", "is_primary_contact"]
