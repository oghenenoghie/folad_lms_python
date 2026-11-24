from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import AcademicYear, School
from apps.students.models import Student

from .models import RouteStop, TransportAssignment, TransportRoute, Vehicle, VehicleMaintenance


class VehicleSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = Vehicle
        fields = ["public_id", "school", "registration_number", "make", "model", "capacity", "status"]


class TransportRouteSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = TransportRoute
        fields = ["public_id", "school", "name", "description"]


class RouteStopSerializer(serializers.ModelSerializer):
    route = PublicIdRelatedField(queryset=TransportRoute.objects)

    class Meta:
        model = RouteStop
        fields = ["public_id", "route", "name", "sequence", "pickup_time"]


class TransportAssignmentSerializer(serializers.ModelSerializer):
    student = PublicIdRelatedField(queryset=Student.objects)
    vehicle = PublicIdRelatedField(queryset=Vehicle.objects)
    route = PublicIdRelatedField(queryset=TransportRoute.objects)
    stop = PublicIdRelatedField(queryset=RouteStop.objects)
    academic_year = PublicIdRelatedField(queryset=AcademicYear.objects)

    class Meta:
        model = TransportAssignment
        fields = [
            "public_id", "student", "vehicle", "route", "stop", "academic_year",
            "assigned_date", "is_active",
        ]
        read_only_fields = ["is_active"]
        extra_kwargs = {"assigned_date": {"required": False}}
        # uq_transport_assignment_one_active_per_student_year (models.py) is a
        # partial unique index (WHERE is_active=True) — DRF's auto-generated
        # UniqueTogetherValidator doesn't know about that condition and would
        # reject a legitimate re-assignment against an already-deactivated row.
        validators = []


class VehicleMaintenanceSerializer(serializers.ModelSerializer):
    vehicle = PublicIdRelatedField(queryset=Vehicle.objects)

    class Meta:
        model = VehicleMaintenance
        fields = [
            "public_id", "vehicle", "description", "cost_minor", "currency_code",
            "scheduled_date", "completed_date", "status",
        ]
