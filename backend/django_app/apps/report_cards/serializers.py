from rest_framework import serializers

from apps.academics.models import Subject
from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import School, Term
from apps.students.models import Student

from .models import ReportCard, ReportCardSubject, ReportCardWeighting


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
            "subjects",
        ]
        read_only_fields = [
            "student", "academic_year", "term", "class_level", "class_arm", "report_card_number",
            "total_score", "total_possible_score", "average_percentage", "class_position", "class_size",
            "attendance_present", "attendance_absent", "attendance_percentage", "status",
            "generated_at", "published_at", "subjects",
        ]


class ReportCardGenerateSerializer(serializers.Serializer):
    student = PublicIdRelatedField(queryset=Student.objects)
    term = PublicIdRelatedField(queryset=Term.objects)


class ReportCardGenerateBulkSerializer(serializers.Serializer):
    term = PublicIdRelatedField(queryset=Term.objects)
    student = PublicIdRelatedField(queryset=Student.objects, many=True, required=False)
