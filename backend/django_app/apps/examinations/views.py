"""Thin views, fat services (§11 ARCHITECTURE.md). Result's four workflow
transitions (submit/review/verify/publish) are dedicated APIView endpoints
rather than a generic PATCH — each has its own permission code so a
deployment can separate duties (e.g. a class teacher enters and submits,
a head of department reviews, an admin verifies and publishes), mirroring
the AcademicYearActivateView/TermActivateView pattern in apps.schools.
Invigilator has no client-facing update: reassigning is unassign-then-
assign (see invigilator_service), so its detail view only supports DELETE.
ReportCard has no client-facing update/delete at all — its status/file_url
are written only by the generate_report_card_pdf Celery task.
"""
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import (
    EnvelopeDestroyMixin,
    EnvelopeRetrieveMixin,
    TenantListAPIView,
    TenantListCreateAPIView,
    TenantRetrieveAPIView,
    TenantRetrieveUpdateDestroyAPIView,
)
from apps.core.responses import envelope, error_envelope
from apps.students.models import Student

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
from .serializers import (
    AssessmentSerializer,
    ExamScheduleSerializer,
    ExamSerializer,
    GradeBandSerializer,
    GradingSchemeSerializer,
    InvigilatorSerializer,
    QuestionOptionSerializer,
    QuestionSerializer,
    ReportCardSerializer,
    ResultSerializer,
    ResultWorkflowStateSerializer,
    StudentAnswerSerializer,
)
from .services import (
    assessment_service,
    exam_schedule_service,
    exam_service,
    grade_band_service,
    grading_scheme_service,
    invigilator_service,
    question_option_service,
    question_service,
    report_card_service,
    result_service,
    student_answer_service,
)
from .services.result_service import InvalidResultTransition
from .services.student_answer_service import InvalidAnswer


class GradingSchemeListCreateView(TenantListCreateAPIView):
    serializer_class = GradingSchemeSerializer

    def get_queryset(self):
        qs = GradingScheme.objects.filter(deleted_at__isnull=True).order_by("name")
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "grading_schemes.create" if self.request.method == "POST" else "grading_schemes.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = grading_scheme_service.create_grading_scheme(
            school=school, actor=self.request.user, **data
        )


class GradingSchemeDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = GradingSchemeSerializer

    def get_queryset(self):
        return GradingScheme.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "grading_schemes.view",
            "PATCH": "grading_schemes.update",
            "DELETE": "grading_schemes.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        grading_scheme_service.update_grading_scheme(
            grading_scheme=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        grading_scheme_service.delete_grading_scheme(grading_scheme=instance, actor=self.request.user)


class GradeBandListCreateView(TenantListCreateAPIView):
    serializer_class = GradeBandSerializer

    def get_queryset(self):
        qs = GradeBand.objects.filter(deleted_at__isnull=True)
        grading_scheme_id = self.request.query_params.get("grading_scheme_id")
        if grading_scheme_id:
            qs = qs.filter(grading_scheme__public_id=grading_scheme_id)
        return qs

    def get_permissions(self):
        code = "grade_bands.create" if self.request.method == "POST" else "grade_bands.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        grading_scheme = data.pop("grading_scheme")
        serializer.instance = grade_band_service.create_grade_band(
            grading_scheme=grading_scheme, actor=self.request.user, **data
        )


class GradeBandDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = GradeBandSerializer

    def get_queryset(self):
        return GradeBand.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "grade_bands.view",
            "PATCH": "grade_bands.update",
            "DELETE": "grade_bands.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("grading_scheme", None)
        grade_band_service.update_grade_band(grade_band=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        grade_band_service.delete_grade_band(grade_band=instance, actor=self.request.user)


class ExamListCreateView(TenantListCreateAPIView):
    serializer_class = ExamSerializer

    def get_queryset(self):
        qs = Exam.objects.filter(deleted_at__isnull=True)
        term_id = self.request.query_params.get("term_id")
        if term_id:
            qs = qs.filter(term__public_id=term_id)
        return qs

    def get_permissions(self):
        code = "exams.create" if self.request.method == "POST" else "exams.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        term = data.pop("term")
        serializer.instance = exam_service.create_exam(term=term, actor=self.request.user, **data)


class ExamDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = ExamSerializer

    def get_queryset(self):
        return Exam.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "exams.view", "PATCH": "exams.update", "DELETE": "exams.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("term", None)
        exam_service.update_exam(exam=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        exam_service.delete_exam(exam=instance, actor=self.request.user)


class ExamScheduleListCreateView(TenantListCreateAPIView):
    serializer_class = ExamScheduleSerializer

    def get_queryset(self):
        qs = ExamSchedule.objects.filter(deleted_at__isnull=True).order_by("date", "start_time")
        exam_id = self.request.query_params.get("exam_id")
        if exam_id:
            qs = qs.filter(exam__public_id=exam_id)
        return qs

    def get_permissions(self):
        code = "exam_schedules.create" if self.request.method == "POST" else "exam_schedules.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        exam = data.pop("exam")
        class_subject = data.pop("class_subject")
        serializer.instance = exam_schedule_service.create_exam_schedule(
            exam=exam, class_subject=class_subject, actor=self.request.user, **data
        )


class ExamScheduleDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = ExamScheduleSerializer

    def get_queryset(self):
        return ExamSchedule.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "exam_schedules.view",
            "PATCH": "exam_schedules.update",
            "DELETE": "exam_schedules.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("exam", None)
        data.pop("class_subject", None)
        exam_schedule_service.update_exam_schedule(
            exam_schedule=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        exam_schedule_service.delete_exam_schedule(exam_schedule=instance, actor=self.request.user)


class InvigilatorListCreateView(TenantListCreateAPIView):
    serializer_class = InvigilatorSerializer

    def get_queryset(self):
        qs = Invigilator.objects.filter(deleted_at__isnull=True)
        exam_schedule_id = self.request.query_params.get("exam_schedule_id")
        if exam_schedule_id:
            qs = qs.filter(exam_schedule__public_id=exam_schedule_id)
        return qs

    def get_permissions(self):
        code = "invigilators.create" if self.request.method == "POST" else "invigilators.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        exam_schedule = data.pop("exam_schedule")
        teacher = data.pop("teacher")
        serializer.instance = invigilator_service.assign_invigilator(
            exam_schedule=exam_schedule, teacher=teacher, actor=self.request.user, **data
        )


class InvigilatorDeleteView(EnvelopeDestroyMixin, generics.GenericAPIView):
    serializer_class = InvigilatorSerializer
    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    def get_queryset(self):
        return Invigilator.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("invigilators.delete")()]

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        invigilator_service.unassign_invigilator(invigilator=instance, actor=self.request.user)


class AssessmentListCreateView(TenantListCreateAPIView):
    serializer_class = AssessmentSerializer

    def get_queryset(self):
        qs = Assessment.objects.filter(deleted_at__isnull=True)
        class_subject_id = self.request.query_params.get("class_subject_id")
        term_id = self.request.query_params.get("term_id")
        if class_subject_id:
            qs = qs.filter(class_subject__public_id=class_subject_id)
        if term_id:
            qs = qs.filter(term__public_id=term_id)
        return qs

    def get_permissions(self):
        code = "assessments.create" if self.request.method == "POST" else "assessments.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        class_subject = data.pop("class_subject")
        term = data.pop("term")
        serializer.instance = assessment_service.create_assessment(
            class_subject=class_subject, term=term, actor=self.request.user, **data
        )


class AssessmentDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = AssessmentSerializer

    def get_queryset(self):
        return Assessment.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "assessments.view",
            "PATCH": "assessments.update",
            "DELETE": "assessments.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("class_subject", None)
        data.pop("term", None)
        assessment_service.update_assessment(assessment=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        assessment_service.delete_assessment(assessment=instance, actor=self.request.user)


class QuestionListCreateView(TenantListCreateAPIView):
    serializer_class = QuestionSerializer

    def get_queryset(self):
        qs = Question.objects.filter(deleted_at__isnull=True)
        assessment_id = self.request.query_params.get("assessment_id")
        if assessment_id:
            qs = qs.filter(assessment__public_id=assessment_id)
        return qs

    def get_permissions(self):
        code = "questions.create" if self.request.method == "POST" else "questions.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        assessment = data.pop("assessment")
        serializer.instance = question_service.create_question(
            assessment=assessment, actor=self.request.user, **data
        )


class QuestionDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = QuestionSerializer

    def get_queryset(self):
        return Question.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "questions.view",
            "PATCH": "questions.update",
            "DELETE": "questions.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("assessment", None)
        question_service.update_question(question=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        question_service.delete_question(question=instance, actor=self.request.user)


class QuestionOptionListCreateView(TenantListCreateAPIView):
    serializer_class = QuestionOptionSerializer

    def get_queryset(self):
        qs = QuestionOption.objects.filter(deleted_at__isnull=True)
        question_id = self.request.query_params.get("question_id")
        if question_id:
            qs = qs.filter(question__public_id=question_id)
        return qs

    def get_permissions(self):
        code = "question_options.create" if self.request.method == "POST" else "question_options.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        question = data.pop("question")
        serializer.instance = question_option_service.create_question_option(
            question=question, actor=self.request.user, **data
        )


class QuestionOptionDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = QuestionOptionSerializer

    def get_queryset(self):
        return QuestionOption.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "question_options.view",
            "PATCH": "question_options.update",
            "DELETE": "question_options.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("question", None)
        question_option_service.update_question_option(
            question_option=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        question_option_service.delete_question_option(
            question_option=instance, actor=self.request.user
        )


class StudentAnswerListCreateView(TenantListCreateAPIView):
    serializer_class = StudentAnswerSerializer

    def get_queryset(self):
        qs = StudentAnswer.objects.filter(deleted_at__isnull=True)
        question_id = self.request.query_params.get("question_id")
        student_id = self.request.query_params.get("student_id")
        if question_id:
            qs = qs.filter(question__public_id=question_id)
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        return qs

    def get_permissions(self):
        code = "student_answers.create" if self.request.method == "POST" else "student_answers.view"
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except InvalidAnswer as exc:
            return error_envelope(str(exc), status=422)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        question = data.pop("question")
        student = data.pop("student")
        serializer.instance = student_answer_service.submit_answer(
            question=question, student=student, actor=self.request.user, **data
        )


class StudentAnswerDetailView(EnvelopeRetrieveMixin, EnvelopeDestroyMixin, generics.GenericAPIView):
    serializer_class = StudentAnswerSerializer
    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    def get_queryset(self):
        return StudentAnswer.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "student_answers.view", "DELETE": "student_answers.delete"}[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        student_answer_service.delete_answer(answer=instance, actor=self.request.user)


class StudentAnswerGradeView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("student_answers.grade")()]

    def post(self, request, public_id):
        try:
            answer = StudentAnswer.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except StudentAnswer.DoesNotExist:
            return error_envelope("student answer not found", status=404)
        if "marks_awarded" not in request.data:
            return error_envelope("marks_awarded is required", status=400)
        try:
            answer = student_answer_service.grade_answer(
                answer=answer,
                actor=request.user,
                marks_awarded=request.data["marks_awarded"],
                is_correct=request.data.get("is_correct"),
            )
        except InvalidAnswer as exc:
            return error_envelope(str(exc), status=422)
        return envelope(StudentAnswerSerializer(answer).data, message="answer graded")


class AssessmentFinalizeScoreView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("results.finalize")()]

    def post(self, request, public_id):
        try:
            assessment = Assessment.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except Assessment.DoesNotExist:
            return error_envelope("assessment not found", status=404)
        student_public_id = request.data.get("student")
        if not student_public_id:
            return error_envelope("student is required", status=400)
        try:
            student = Student.objects.get(public_id=student_public_id)
        except Student.DoesNotExist:
            return error_envelope("student not found", status=404)
        try:
            result = student_answer_service.finalize_assessment_score(
                assessment=assessment, student=student, actor=request.user
            )
        except (InvalidAnswer, InvalidResultTransition) as exc:
            return error_envelope(str(exc), status=409)
        return envelope(ResultSerializer(result).data, message="score finalized")


class ResultListCreateView(TenantListCreateAPIView):
    serializer_class = ResultSerializer

    def get_queryset(self):
        qs = Result.objects.filter(deleted_at__isnull=True)
        assessment_id = self.request.query_params.get("assessment_id")
        student_id = self.request.query_params.get("student_id")
        if assessment_id:
            qs = qs.filter(assessment__public_id=assessment_id)
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        return qs

    def get_permissions(self):
        code = "results.create" if self.request.method == "POST" else "results.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        assessment = data.pop("assessment")
        student = data.pop("student")
        serializer.instance = result_service.enter_result(
            assessment=assessment, student=student, actor=self.request.user, **data
        )


class ResultDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = ResultSerializer

    def get_queryset(self):
        return Result.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "results.view", "PATCH": "results.update", "DELETE": "results.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except InvalidResultTransition as exc:
            return error_envelope(str(exc), status=409)

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("assessment", None)
        data.pop("student", None)
        result_service.update_result(result=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        result_service.delete_result(result=instance, actor=self.request.user)


class _ResultTransitionView(APIView):
    permission_code = None

    def get_permissions(self):
        return [IsAuthenticated(), require_permission(self.permission_code)()]

    def post(self, request, public_id):
        try:
            result = Result.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except Result.DoesNotExist:
            return error_envelope("result not found", status=404)
        try:
            self.transition(result=result, actor=request.user)
        except InvalidResultTransition as exc:
            return error_envelope(str(exc), status=409)
        return envelope(ResultSerializer(result).data, message=f"result {result.status}")

    def transition(self, *, result, actor):
        raise NotImplementedError


class ResultSubmitView(_ResultTransitionView):
    permission_code = "results.submit"

    def transition(self, *, result, actor):
        result_service.submit_result(result=result, actor=actor)


class ResultReviewView(_ResultTransitionView):
    permission_code = "results.review"

    def transition(self, *, result, actor):
        result_service.review_result(result=result, actor=actor)


class ResultVerifyView(_ResultTransitionView):
    permission_code = "results.verify"

    def transition(self, *, result, actor):
        result_service.verify_result(result=result, actor=actor)


class ResultPublishView(_ResultTransitionView):
    permission_code = "results.publish"

    def transition(self, *, result, actor):
        result_service.publish_result(result=result, actor=actor)


class ResultWorkflowStateListView(TenantListAPIView):
    serializer_class = ResultWorkflowStateSerializer

    def get_queryset(self):
        qs = ResultWorkflowState.objects.all()
        result_id = self.request.query_params.get("result_id")
        if result_id:
            qs = qs.filter(result__public_id=result_id)
        return qs

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("results.view")()]


class ReportCardListCreateView(TenantListCreateAPIView):
    serializer_class = ReportCardSerializer

    def get_queryset(self):
        qs = ReportCard.objects.filter(deleted_at__isnull=True)
        student_id = self.request.query_params.get("student_id")
        term_id = self.request.query_params.get("term_id")
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        if term_id:
            qs = qs.filter(term__public_id=term_id)
        return qs

    def get_permissions(self):
        code = "report_cards.create" if self.request.method == "POST" else "report_cards.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        student = data.pop("student")
        term = data.pop("term")
        serializer.instance = report_card_service.request_report_card(
            student=student, academic_year=term.academic_year, term=term, actor=self.request.user
        )


class ReportCardDetailView(TenantRetrieveAPIView):
    serializer_class = ReportCardSerializer

    def get_queryset(self):
        return ReportCard.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.view")()]
