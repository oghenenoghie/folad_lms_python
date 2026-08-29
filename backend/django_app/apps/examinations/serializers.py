from rest_framework import serializers

from apps.academics.models import ClassSubject
from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import School, Term
from apps.staff.models import Teacher
from apps.students.models import Student
from apps.timetable.models import Room

from .models import (
    Assessment,
    Exam,
    ExamSchedule,
    GradeBand,
    GradingScheme,
    Invigilator,
    Question,
    QuestionOption,
    ReportCard,
    Result,
    ResultWorkflowState,
    StudentAnswer,
)


class GradingSchemeSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = GradingScheme
        fields = ["public_id", "school", "name", "is_default"]


class GradeBandSerializer(serializers.ModelSerializer):
    grading_scheme = PublicIdRelatedField(queryset=GradingScheme.objects)

    class Meta:
        model = GradeBand
        fields = ["public_id", "grading_scheme", "grade", "min_score", "max_score", "remark"]


class ExamSerializer(serializers.ModelSerializer):
    term = PublicIdRelatedField(queryset=Term.objects)
    school = PublicIdRelatedField(read_only=True)
    academic_year = PublicIdRelatedField(read_only=True)

    class Meta:
        model = Exam
        fields = ["public_id", "school", "academic_year", "term", "name", "start_date", "end_date"]


class ExamScheduleSerializer(serializers.ModelSerializer):
    exam = PublicIdRelatedField(queryset=Exam.objects)
    class_subject = PublicIdRelatedField(queryset=ClassSubject.objects)
    room = PublicIdRelatedField(queryset=Room.objects, required=False, allow_null=True)

    class Meta:
        model = ExamSchedule
        fields = ["public_id", "exam", "class_subject", "date", "start_time", "end_time", "room"]
        validators = []


class InvigilatorSerializer(serializers.ModelSerializer):
    exam_schedule = PublicIdRelatedField(queryset=ExamSchedule.objects)
    teacher = PublicIdRelatedField(queryset=Teacher.objects)

    class Meta:
        model = Invigilator
        fields = ["public_id", "exam_schedule", "teacher"]
        validators = []


class AssessmentSerializer(serializers.ModelSerializer):
    class_subject = PublicIdRelatedField(queryset=ClassSubject.objects)
    term = PublicIdRelatedField(queryset=Term.objects)
    exam = PublicIdRelatedField(queryset=Exam.objects, required=False, allow_null=True)

    class Meta:
        model = Assessment
        fields = [
            "public_id",
            "class_subject",
            "term",
            "exam",
            "name",
            "assessment_type",
            "weight",
            "max_score",
        ]
        validators = []


class QuestionSerializer(serializers.ModelSerializer):
    assessment = PublicIdRelatedField(queryset=Assessment.objects)

    class Meta:
        model = Question
        fields = ["public_id", "assessment", "question_type", "text", "marks", "sequence"]
        validators = []


class QuestionOptionSerializer(serializers.ModelSerializer):
    question = PublicIdRelatedField(queryset=Question.objects)

    class Meta:
        model = QuestionOption
        fields = ["public_id", "question", "text", "is_correct", "sequence"]
        validators = []


class StudentAnswerSerializer(serializers.ModelSerializer):
    question = PublicIdRelatedField(queryset=Question.objects)
    student = PublicIdRelatedField(queryset=Student.objects)
    selected_option = PublicIdRelatedField(
        queryset=QuestionOption.objects, required=False, allow_null=True
    )

    class Meta:
        model = StudentAnswer
        fields = [
            "public_id",
            "question",
            "student",
            "selected_option",
            "text_answer",
            "is_correct",
            "marks_awarded",
            "submitted_at",
        ]
        read_only_fields = ["is_correct", "marks_awarded", "submitted_at"]
        validators = []


class ResultSerializer(serializers.ModelSerializer):
    assessment = PublicIdRelatedField(queryset=Assessment.objects)
    student = PublicIdRelatedField(queryset=Student.objects)

    class Meta:
        model = Result
        fields = ["public_id", "assessment", "student", "score", "grade", "remark", "status"]
        read_only_fields = ["grade", "remark", "status"]
        validators = []


class ResultWorkflowStateSerializer(serializers.ModelSerializer):
    result = PublicIdRelatedField(read_only=True)
    changed_by = serializers.SerializerMethodField()

    class Meta:
        model = ResultWorkflowState
        fields = ["public_id", "result", "previous_status", "new_status", "changed_by", "created_at"]

    def get_changed_by(self, obj: ResultWorkflowState) -> str | None:
        return str(obj.changed_by.public_id) if obj.changed_by_id else None


class ReportCardSerializer(serializers.ModelSerializer):
    student = PublicIdRelatedField(queryset=Student.objects)
    # Always derived server-side from `term` (see report_card_service.request_report_card).
    academic_year = PublicIdRelatedField(read_only=True)
    term = PublicIdRelatedField(queryset=Term.objects)

    class Meta:
        model = ReportCard
        fields = [
            "public_id",
            "student",
            "academic_year",
            "term",
            "status",
            "file_url",
            "generated_at",
            "error_message",
        ]
        read_only_fields = ["status", "file_url", "generated_at", "error_message"]
