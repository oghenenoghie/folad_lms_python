from rest_framework import serializers

from apps.accounts.models import User
from apps.core.serializers import PublicIdRelatedField
from apps.core.storage import get_presigned_download_url
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
    # Set only on the in-memory instance student_service.create_student()
    # returns right after auto-provisioning a login — never persisted,
    # never present on a student re-fetched from the DB, so this is the
    # one and only time the plaintext password is ever visible.
    generated_password = serializers.SerializerMethodField()
    # A freshly computed presigned URL (or None), never the raw storage
    # key — same read-only, compute-at-request-time convention as
    # apps.documents/apps.assignments' download endpoints.
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "public_id",
            "school",
            "user",
            "admission_number",
            "first_name",
            "last_name",
            "email",
            "date_of_birth",
            "gender",
            "enrollment_status",
            "generated_password",
            "photo_url",
        ]
        # Both fields of uq_student_school_admission_number are serializer
        # fields, so DRF would otherwise auto-add a UniqueTogetherValidator
        # that bypasses the envelope with a raw 400 instead of the clean
        # 409 the EnvelopeCreateMixin IntegrityError handler produces (see
        # core/generics.py).
        validators = []

    def get_generated_password(self, obj):
        return getattr(obj, "_generated_password", None)

    def get_photo_url(self, obj):
        return get_presigned_download_url(obj.photo_storage_key) if obj.photo_storage_key else None
