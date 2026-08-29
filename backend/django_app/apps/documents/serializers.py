from rest_framework import serializers

from apps.core.serializers import PublicIdRelatedField
from apps.staff.models import Staff
from apps.students.models import Student

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    student = PublicIdRelatedField(read_only=True)
    staff = PublicIdRelatedField(read_only=True)
    uploaded_by = PublicIdRelatedField(read_only=True)

    class Meta:
        model = Document
        fields = [
            "public_id", "owner_type", "student", "staff", "document_type", "title",
            "file_name", "content_type", "size_bytes", "uploaded_by", "created_at",
        ]
        read_only_fields = [
            "owner_type", "file_name", "content_type", "size_bytes", "uploaded_by", "created_at",
        ]


# Used only by DocumentUploadView to validate the non-file form fields of a
# multipart upload — never for output, and never handles the file itself
# (that comes from request.FILES, outside DRF's serializer validation).
class DocumentUploadSerializer(serializers.Serializer):
    document_type = serializers.CharField(max_length=50)
    title = serializers.CharField(max_length=200)
    student = PublicIdRelatedField(queryset=Student.objects, required=False, allow_null=True)
    staff = PublicIdRelatedField(queryset=Staff.objects, required=False, allow_null=True)
