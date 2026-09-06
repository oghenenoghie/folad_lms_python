from rest_framework import serializers

from apps.academics.models import ClassLevel, Subject
from apps.core.serializers import PublicIdRelatedField
from apps.core.storage import get_presigned_download_url
from apps.schools.models import AcademicYear, School, Term
from apps.students.models import Student

from .models import (
    CBTExam,
    CBTMedia,
    ExamCandidate,
    ExamQuestion,
    ExamSection,
    Question,
    QuestionBlock,
    QuestionOption,
    QuestionVersion,
    Topic,
)


class TopicSerializer(serializers.ModelSerializer):
    subject = PublicIdRelatedField(queryset=Subject.objects)

    class Meta:
        model = Topic
        fields = ["public_id", "subject", "name", "is_active"]


class QuestionBlockSerializer(serializers.ModelSerializer):
    question = PublicIdRelatedField(read_only=True)

    class Meta:
        model = QuestionBlock
        fields = ["public_id", "question", "block_type", "content", "order"]


class QuestionOptionSerializer(serializers.ModelSerializer):
    question = PublicIdRelatedField(read_only=True)

    class Meta:
        model = QuestionOption
        fields = ["public_id", "question", "label", "content", "is_correct", "order", "explanation"]


class QuestionSerializer(serializers.ModelSerializer):
    """Flat, shell-only fields — a question's content lives entirely in its
    `blocks`/`options` sub-resources (see QuestionBlockListCreateView/
    QuestionOptionListCreateView), matching the same "one endpoint per
    concern" convention apps.examinations.QuestionOptionSerializer already
    uses rather than a single nested writable serializer.
    """

    subject = PublicIdRelatedField(queryset=Subject.objects)
    class_level = PublicIdRelatedField(queryset=ClassLevel.objects)
    topic = PublicIdRelatedField(queryset=Topic.objects, required=False, allow_null=True)
    status = serializers.CharField(read_only=True)
    approved_by = serializers.SerializerMethodField()
    blocks = QuestionBlockSerializer(many=True, read_only=True)
    options = QuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "public_id",
            "code",
            "subject",
            "class_level",
            "topic",
            "question_type",
            "difficulty",
            "marks",
            "negative_marks",
            "status",
            "approved_by",
            "blocks",
            "options",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["code"]

    def get_approved_by(self, obj: Question) -> str | None:
        return str(obj.approved_by.public_id) if obj.approved_by_id else None


class QuestionVersionSerializer(serializers.ModelSerializer):
    question = PublicIdRelatedField(read_only=True)

    class Meta:
        model = QuestionVersion
        fields = ["public_id", "question", "version_number", "content", "created_at"]


class CBTMediaSerializer(serializers.ModelSerializer):
    """`storage_key` is never exposed — like apps.documents, a fresh
    presigned `download_url` is computed per request instead (see the
    module docstring on apps.core.storage: "a fresh presigned URL... rather
    than persisting one that will eventually expire").
    """

    download_url = serializers.SerializerMethodField()

    class Meta:
        model = CBTMedia
        fields = [
            "public_id",
            "name",
            "media_type",
            "content_type",
            "size_bytes",
            "width",
            "height",
            "alt_text",
            "caption",
            "download_url",
            "created_at",
        ]

    def get_download_url(self, obj: CBTMedia) -> str:
        return get_presigned_download_url(obj.storage_key)


class CBTExamSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)
    academic_year = PublicIdRelatedField(queryset=AcademicYear.objects)
    term = PublicIdRelatedField(queryset=Term.objects)
    subject = PublicIdRelatedField(queryset=Subject.objects)
    class_level = PublicIdRelatedField(queryset=ClassLevel.objects)
    code = serializers.CharField(read_only=True)
    total_marks = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)
    published_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = CBTExam
        fields = [
            "public_id",
            "code",
            "school",
            "academic_year",
            "term",
            "subject",
            "class_level",
            "name",
            "exam_type",
            "duration_minutes",
            "total_marks",
            "pass_mark",
            "instructions",
            "randomize_questions",
            "randomize_options",
            "allow_resume",
            "negative_marking",
            "status",
            "start_at",
            "end_at",
            "published_at",
            "created_at",
        ]


class ExamSectionSerializer(serializers.ModelSerializer):
    exam = PublicIdRelatedField(read_only=True)

    class Meta:
        model = ExamSection
        fields = ["public_id", "exam", "name", "instructions", "order", "marks"]


class ExamQuestionSerializer(serializers.ModelSerializer):
    exam = PublicIdRelatedField(read_only=True)
    question = PublicIdRelatedField(queryset=Question.objects)
    section = PublicIdRelatedField(queryset=ExamSection.objects, required=False, allow_null=True)
    snapshot = serializers.JSONField(read_only=True)
    effective_marks = serializers.SerializerMethodField()

    class Meta:
        model = ExamQuestion
        fields = [
            "public_id",
            "exam",
            "question",
            "section",
            "order",
            "marks_override",
            "effective_marks",
            "snapshot",
        ]

    def get_effective_marks(self, obj: ExamQuestion) -> str:
        return str(obj.marks)


class ExamCandidateSerializer(serializers.ModelSerializer):
    exam = PublicIdRelatedField(read_only=True)
    student = PublicIdRelatedField(queryset=Student.objects)
    candidate_number = serializers.CharField(read_only=True)

    class Meta:
        model = ExamCandidate
        fields = [
            "public_id",
            "exam",
            "student",
            "candidate_number",
            "extra_time_minutes",
            "is_eligible",
        ]
