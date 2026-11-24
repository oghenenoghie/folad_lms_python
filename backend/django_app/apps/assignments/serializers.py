from rest_framework import serializers

from apps.academics.models import ClassSubject
from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import Term
from apps.students.models import Student

from .models import Assignment, AssignmentSubmission


class AssignmentSerializer(serializers.ModelSerializer):
    class_subject = PublicIdRelatedField(queryset=ClassSubject.objects)
    term = PublicIdRelatedField(queryset=Term.objects)

    class Meta:
        model = Assignment
        fields = ["public_id", "class_subject", "term", "title", "description", "due_date", "max_score"]


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    assignment = PublicIdRelatedField(queryset=Assignment.objects)
    student = PublicIdRelatedField(queryset=Student.objects)

    class Meta:
        model = AssignmentSubmission
        fields = [
            "public_id", "assignment", "student", "text_content", "file_name", "content_type",
            "size_bytes", "submitted_at", "status", "score", "feedback", "graded_at",
        ]
        read_only_fields = [
            "file_name", "content_type", "size_bytes", "submitted_at", "status", "score",
            "feedback", "graded_at",
        ]
        extra_kwargs = {"text_content": {"required": False}}
        # uq_assignment_submission_assignment_student uses Meta.constraints,
        # not the legacy unique_together — DRF still auto-adds a
        # UniqueTogetherValidator for it, which would bypass the envelope
        # with a raw 400 instead of the clean 409 the EnvelopeCreateMixin
        # IntegrityError handler produces (see core/generics.py).
        validators = []
