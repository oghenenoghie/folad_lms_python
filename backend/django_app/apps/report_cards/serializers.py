from rest_framework import serializers

from apps.academics.models import ClassArm
from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import School, Term
from apps.students.models import Student

from .models import (
    PsychomotorRating,
    PsychomotorTrait,
    ReportCard,
    ReportCardAudit,
    ReportCardBulkExport,
    ReportCardSubject,
    ReportCardWeighting,
)
from .services.report_card_service import InvalidPsychomotorRating, set_psychomotor_ratings


class ReportCardWeightingSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = ReportCardWeighting
        fields = ["public_id", "school", "ca_weight", "cbt_weight", "exam_weight"]

    def validate(self, attrs):
        ca = attrs.get("ca_weight", getattr(self.instance, "ca_weight", None))
        cbt = attrs.get("cbt_weight", getattr(self.instance, "cbt_weight", None))
        exam = attrs.get("exam_weight", getattr(self.instance, "exam_weight", None))
        if ca is not None and cbt is not None and exam is not None and (ca + cbt + exam) != 100:
            raise serializers.ValidationError("ca_weight + cbt_weight + exam_weight must add up to 100")
        return attrs


class ReportCardSubjectSerializer(serializers.ModelSerializer):
    # Nested read-only under ReportCardSerializer (see read_only_fields
    # below) — a display name, not an editable relation, so this returns
    # the subject's name directly rather than its public_id. Mirrors
    # ReportCardVerifySubjectSerializer's identical field.
    subject = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = ReportCardSubject
        fields = [
            "public_id",
            "subject",
            "ca_score",
            "ca_max_score",
            "cbt_score",
            "cbt_max_score",
            "exam_score",
            "exam_max_score",
            "total_score",
            "percentage",
            "grade",
            "remark",
            "class_position",
            "class_average",
            "teacher_comment",
        ]
        read_only_fields = [f for f in fields if f not in ("teacher_comment",)]


class PsychomotorTraitSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = PsychomotorTrait
        fields = ["public_id", "school", "name", "order"]


class PsychomotorRatingSerializer(serializers.ModelSerializer):
    # Nested writable under ReportCardSerializer (see its update() override)
    # — a teacher submits {"trait": <public_id>, "rating": 1-5} per row;
    # trait_name/rating_label are read-only display conveniences so a
    # client doesn't have to cross-reference the traits list just to show
    # what was submitted.
    trait = PublicIdRelatedField(queryset=PsychomotorTrait.objects)
    trait_name = serializers.CharField(source="trait.name", read_only=True)
    rating_label = serializers.CharField(source="get_rating_display", read_only=True)

    class Meta:
        model = PsychomotorRating
        fields = ["trait", "trait_name", "rating", "rating_label"]


class ReportCardSerializer(serializers.ModelSerializer):
    student = PublicIdRelatedField(queryset=Student.objects)
    academic_year = PublicIdRelatedField(read_only=True)
    term = PublicIdRelatedField(read_only=True)
    class_level = PublicIdRelatedField(read_only=True)
    class_arm = PublicIdRelatedField(read_only=True)
    subjects = ReportCardSubjectSerializer(many=True, read_only=True)
    # Writable, unlike every other nested/calculated field here — see
    # update() below. A teacher submits the whole current set of ratings
    # each time; anything the payload doesn't mention keeps its existing
    # value (see set_psychomotor_ratings's own docstring).
    psychomotor_ratings = PsychomotorRatingSerializer(many=True, required=False)

    class Meta:
        model = ReportCard
        fields = [
            "public_id",
            "student",
            "academic_year",
            "term",
            "class_level",
            "class_arm",
            "report_card_number",
            "verification_code",
            "total_score",
            "total_possible_score",
            "average_percentage",
            "overall_grade",
            "overall_remark",
            "class_position",
            "class_size",
            "attendance_present",
            "attendance_absent",
            "attendance_percentage",
            "teacher_comment",
            "principal_comment",
            "next_term_begins",
            "status",
            "generated_at",
            "published_at",
            "pdf_status",
            "pdf_generated_at",
            "pdf_error_message",
            "subjects",
            "psychomotor_ratings",
        ]
        read_only_fields = [
            "student", "academic_year", "term", "class_level", "class_arm", "report_card_number",
            "verification_code", "total_score", "total_possible_score", "average_percentage",
            "overall_grade", "overall_remark", "class_position", "class_size", "attendance_present",
            "attendance_absent", "attendance_percentage", "status", "generated_at", "published_at",
            "pdf_status", "pdf_generated_at", "pdf_error_message", "subjects",
        ]

    def update(self, instance, validated_data):
        ratings_data = validated_data.pop("psychomotor_ratings", None)
        instance = super().update(instance, validated_data)
        if ratings_data is not None:
            ratings = {row["trait"].id: row["rating"] for row in ratings_data}
            try:
                set_psychomotor_ratings(
                    report_card=instance, ratings=ratings, actor=self.context["request"].user
                )
            except InvalidPsychomotorRating as exc:
                raise serializers.ValidationError({"psychomotor_ratings": str(exc)}) from exc
            instance.refresh_from_db()
        return instance


class ReportCardAuditSerializer(serializers.ModelSerializer):
    report_card = PublicIdRelatedField(read_only=True)
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = ReportCardAudit
        fields = ["public_id", "report_card", "action", "previous_status", "new_status", "changed_by", "created_at"]

    def get_changed_by(self, obj: ReportCardAudit) -> str | None:
        return str(obj.changed_by.public_id) if obj.changed_by_id else None


class ReportCardGenerateSerializer(serializers.Serializer):
    student = PublicIdRelatedField(queryset=Student.objects)
    term = PublicIdRelatedField(queryset=Term.objects)


class ReportCardGenerateBulkSerializer(serializers.Serializer):
    term = PublicIdRelatedField(queryset=Term.objects)
    student = PublicIdRelatedField(queryset=Student.objects, many=True, required=False)


class ReportCardBulkExportSerializer(serializers.ModelSerializer):
    term = PublicIdRelatedField(read_only=True)
    class_arm = PublicIdRelatedField(read_only=True)

    class Meta:
        model = ReportCardBulkExport
        fields = [
            "public_id",
            "term",
            "class_arm",
            "status",
            "report_card_count",
            "failed_count",
            "file_url",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields


class ReportCardBulkExportRequestSerializer(serializers.Serializer):
    term = PublicIdRelatedField(queryset=Term.objects)
    # Omitted means "every student enrolled this academic year" — see
    # ReportCardBulkExport.class_arm's docstring.
    class_arm = PublicIdRelatedField(queryset=ClassArm.objects, required=False)


class ReportCardVerifySubjectSerializer(serializers.Serializer):
    """Mirrors the subject columns printed on the PDF (see
    report_card_pdf_service._subjects_table) so a third party can check
    a physical/printed report card line-by-line against this response —
    that's the entire point of a verification lookup. Deliberately
    excludes teacher_comment: not needed to confirm authenticity, and
    more personal than the rest of this already-public-on-paper data.
    """

    subject = serializers.CharField(source="subject.name")
    ca_score = serializers.DecimalField(max_digits=6, decimal_places=2)
    cbt_score = serializers.DecimalField(max_digits=6, decimal_places=2)
    exam_score = serializers.DecimalField(max_digits=6, decimal_places=2)
    total_score = serializers.DecimalField(max_digits=6, decimal_places=2)
    percentage = serializers.DecimalField(max_digits=6, decimal_places=2)
    grade = serializers.CharField()
    remark = serializers.CharField()
    class_average = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True)


class ReportCardVerifySerializer(serializers.Serializer):
    """The public verification payload — everything a QR-code scan or a
    manual code lookup returns. No teacher_comment/principal_comment: see
    ReportCardVerifySubjectSerializer's docstring for why.
    """

    report_card_number = serializers.CharField()
    verification_code = serializers.CharField()
    student_name = serializers.SerializerMethodField()
    school_name = serializers.CharField(source="student.school.name")
    class_name = serializers.SerializerMethodField()
    academic_year = serializers.CharField(source="academic_year.name")
    term = serializers.CharField(source="term.name")
    total_score = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_possible_score = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_percentage = serializers.DecimalField(max_digits=6, decimal_places=2)
    overall_grade = serializers.CharField()
    overall_remark = serializers.CharField()
    class_position = serializers.IntegerField()
    class_size = serializers.IntegerField()
    attendance_percentage = serializers.DecimalField(max_digits=6, decimal_places=2)
    status = serializers.CharField()
    generated_at = serializers.DateTimeField()
    published_at = serializers.DateTimeField()
    subjects = ReportCardVerifySubjectSerializer(source="subjects.all", many=True)
    psychomotor_ratings = PsychomotorRatingSerializer(source="psychomotor_ratings.all", many=True)

    def get_student_name(self, obj) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_class_name(self, obj) -> str:
        return f"{obj.class_level.name} {obj.class_arm.name}"
