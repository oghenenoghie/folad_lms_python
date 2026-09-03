from rest_framework import serializers

from apps.academics.models import ClassArm, Subject
from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import School, Term
from apps.students.models import Student

from .models import ReportCard, ReportCardAudit, ReportCardBulkExport, ReportCardSubject, ReportCardWeighting


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
    subject = PublicIdRelatedField(queryset=Subject.objects)

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
            "teacher_comment",
        ]
        read_only_fields = [f for f in fields if f not in ("teacher_comment",)]


class ReportCardSerializer(serializers.ModelSerializer):
    student = PublicIdRelatedField(queryset=Student.objects)
    academic_year = PublicIdRelatedField(read_only=True)
    term = PublicIdRelatedField(read_only=True)
    class_level = PublicIdRelatedField(read_only=True)
    class_arm = PublicIdRelatedField(read_only=True)
    subjects = ReportCardSubjectSerializer(many=True, read_only=True)

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
        ]
        read_only_fields = [
            "student", "academic_year", "term", "class_level", "class_arm", "report_card_number",
            "verification_code", "total_score", "total_possible_score", "average_percentage",
            "class_position", "class_size", "attendance_present", "attendance_absent",
            "attendance_percentage", "status", "generated_at", "published_at", "pdf_status",
            "pdf_generated_at", "pdf_error_message", "subjects",
        ]


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
    class_position = serializers.IntegerField()
    class_size = serializers.IntegerField()
    attendance_percentage = serializers.DecimalField(max_digits=6, decimal_places=2)
    status = serializers.CharField()
    generated_at = serializers.DateTimeField()
    published_at = serializers.DateTimeField()
    subjects = ReportCardVerifySubjectSerializer(source="subjects.all", many=True)

    def get_student_name(self, obj) -> str:
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_class_name(self, obj) -> str:
        return f"{obj.class_level.name} {obj.class_arm.name}"
