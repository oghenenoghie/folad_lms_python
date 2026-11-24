from rest_framework import serializers

from apps.academics.models import Enrollment
from apps.core.serializers import PublicIdRelatedField

from .models import Attendance, AttendanceAudit


class AttendanceSerializer(serializers.ModelSerializer):
    # `Enrollment.objects` (the manager), not `.all()` — DRF's RelatedField
    # re-evaluates a bare manager's `.all()` lazily per-request, whereas a
    # pre-built queryset would freeze TenantManager's org-scoping at import
    # time (no request context yet), permanently baking in an empty set.
    enrollment = PublicIdRelatedField(queryset=Enrollment.objects)

    class Meta:
        model = Attendance
        fields = ["public_id", "enrollment", "date", "status", "remarks"]
        # Both fields of uq_attendance_enrollment_date are serializer
        # fields, so DRF would otherwise auto-add a UniqueTogetherValidator
        # that bypasses the envelope with a raw 400 instead of the clean
        # 409 the EnvelopeCreateMixin IntegrityError handler produces (see
        # core/generics.py).
        validators = []


class AttendanceAuditSerializer(serializers.ModelSerializer):
    attendance = PublicIdRelatedField(read_only=True)
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceAudit
        fields = ["public_id", "attendance", "previous_status", "new_status", "changed_by", "created_at"]

    def get_changed_by(self, obj: AttendanceAudit) -> str | None:
        return str(obj.changed_by.public_id) if obj.changed_by_id else None
