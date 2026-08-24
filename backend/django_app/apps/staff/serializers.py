from rest_framework import serializers

from apps.accounts.models import User
from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import Department, School

from .models import Staff, Teacher


class StaffSerializer(serializers.ModelSerializer):
    # Managers, not `.all()` — see students/serializers.py's note on why.
    school = PublicIdRelatedField(queryset=School.objects)
    department = PublicIdRelatedField(queryset=Department.objects, required=False, allow_null=True)
    user = PublicIdRelatedField(queryset=User.objects, required=False, allow_null=True)

    class Meta:
        model = Staff
        fields = [
            "public_id",
            "school",
            "department",
            "user",
            "employee_number",
            "first_name",
            "last_name",
            "position",
            "employment_status",
            "date_joined",
        ]


class TeacherSerializer(serializers.ModelSerializer):
    staff = PublicIdRelatedField(queryset=Staff.objects)

    class Meta:
        model = Teacher
        fields = ["public_id", "staff", "qualification", "specialization"]
