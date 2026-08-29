from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import School

from .models import ReportRequest


class ReportRequestSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)
    requested_by = PublicIdRelatedField(read_only=True)

    class Meta:
        model = ReportRequest
        fields = [
            "public_id", "school", "report_type", "format", "parameters", "status",
            "file_name", "content_type", "requested_by", "generated_at", "error_message", "created_at",
        ]
        read_only_fields = [
            "status", "file_name", "content_type", "requested_by", "generated_at", "error_message",
            "created_at",
        ]
