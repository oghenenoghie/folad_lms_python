from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import AcademicYear, School
from apps.staff.models import Staff
from apps.students.models import Student

from .models import Hostel, HostelAllocation, HostelBed, HostelBuilding, HostelIncident, HostelRoom


class HostelSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)
    warden = PublicIdRelatedField(queryset=Staff.objects, required=False, allow_null=True)

    class Meta:
        model = Hostel
        fields = ["public_id", "school", "name", "hostel_type", "warden"]


class HostelBuildingSerializer(serializers.ModelSerializer):
    hostel = PublicIdRelatedField(queryset=Hostel.objects)

    class Meta:
        model = HostelBuilding
        fields = ["public_id", "hostel", "name"]


class HostelRoomSerializer(serializers.ModelSerializer):
    building = PublicIdRelatedField(queryset=HostelBuilding.objects)

    class Meta:
        model = HostelRoom
        fields = ["public_id", "building", "room_number", "capacity"]


class HostelBedSerializer(serializers.ModelSerializer):
    room = PublicIdRelatedField(queryset=HostelRoom.objects)

    class Meta:
        model = HostelBed
        fields = ["public_id", "room", "bed_number", "status"]
        read_only_fields = ["status"]


class HostelAllocationSerializer(serializers.ModelSerializer):
    student = PublicIdRelatedField(queryset=Student.objects)
    bed = PublicIdRelatedField(queryset=HostelBed.objects)
    academic_year = PublicIdRelatedField(queryset=AcademicYear.objects)

    class Meta:
        model = HostelAllocation
        fields = [
            "public_id", "student", "bed", "academic_year", "allocated_date", "vacated_date", "is_active",
        ]
        read_only_fields = ["vacated_date", "is_active"]
        extra_kwargs = {"allocated_date": {"required": False}}
        # Both uq_hostel_allocation_one_active_per_bed and
        # uq_hostel_allocation_one_active_per_student_year (models.py) are
        # partial unique indexes (WHERE is_active=True) — see the matching
        # note on TransportAssignmentSerializer.
        validators = []


class HostelIncidentSerializer(serializers.ModelSerializer):
    hostel = PublicIdRelatedField(queryset=Hostel.objects)
    room = PublicIdRelatedField(queryset=HostelRoom.objects, required=False, allow_null=True)
    student = PublicIdRelatedField(queryset=Student.objects, required=False, allow_null=True)
    reported_by = serializers.SerializerMethodField()

    class Meta:
        model = HostelIncident
        fields = [
            "public_id", "hostel", "room", "student", "reported_by", "description", "severity",
            "status", "occurred_at", "resolved_at",
        ]
        read_only_fields = ["status", "resolved_at"]

    def get_reported_by(self, obj: HostelIncident) -> str | None:
        return str(obj.reported_by.public_id) if obj.reported_by_id else None
