from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField

from .models import AcademicYear, Campus, Department, School, Term


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = [
            "public_id",
            "name",
            "code",
            "address",
            "phone",
            "email",
            "default_grading_scheme",
            "is_active",
        ]


class CampusSerializer(serializers.ModelSerializer):
    # `School.objects` (the manager), not `.all()` — DRF's RelatedField
    # re-evaluates a bare manager's `.all()` lazily per-request, whereas a
    # pre-built queryset would freeze TenantManager's org-scoping at import
    # time (no request context yet), permanently baking in an empty set.
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = Campus
        fields = ["public_id", "school", "name", "code", "address", "is_main", "is_active"]


class AcademicYearSerializer(serializers.ModelSerializer):
    # `School.objects` (the manager), not `.all()` — DRF's RelatedField
    # re-evaluates a bare manager's `.all()` lazily per-request, whereas a
    # pre-built queryset would freeze TenantManager's org-scoping at import
    # time (no request context yet), permanently baking in an empty set.
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = AcademicYear
        fields = ["public_id", "school", "name", "start_date", "end_date", "is_current", "is_active"]
        read_only_fields = ["is_current"]


class TermSerializer(serializers.ModelSerializer):
    academic_year = PublicIdRelatedField(queryset=AcademicYear.objects)

    class Meta:
        model = Term
        fields = [
            "public_id",
            "academic_year",
            "name",
            "sequence",
            "start_date",
            "end_date",
            "is_current",
            "is_active",
        ]
        read_only_fields = ["is_current"]


class DepartmentSerializer(serializers.ModelSerializer):
    # `School.objects` (the manager), not `.all()` — DRF's RelatedField
    # re-evaluates a bare manager's `.all()` lazily per-request, whereas a
    # pre-built queryset would freeze TenantManager's org-scoping at import
    # time (no request context yet), permanently baking in an empty set.
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = Department
        fields = ["public_id", "school", "name", "code", "description", "is_active"]
