"""Thin views, fat services (§11 ARCHITECTURE.md) — same convention as
apps.examinations/apps.report_cards. QuestionBlock/QuestionOption are
nested under their Question in the URL (they're pure sub-resources of a
question's content, not independently permissioned or listed) rather than
top-level endpoints the way apps.examinations.QuestionOption is — see the
CBT spec's own API section for why nesting is the right call here.
"""
from decimal import Decimal, InvalidOperation

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.academics.models import ClassLevel, Subject
from apps.accounts.permissions import require_permission
from apps.core.generics import (
    TenantListAPIView,
    TenantListCreateAPIView,
    TenantRetrieveUpdateDestroyAPIView,
)
from apps.core.responses import envelope, error_envelope

from .models import (
    CBTExam,
    CBTMedia,
    CBTImportJob,
    ExamAttempt,
    ExamCandidate,
    ExamQuestion,
    ExamSection,
    Question,
    QuestionBlock,
    QuestionOption,
    QuestionVersion,
    StudentAnswer,
    Topic,
)
from .serializers import (
    AttemptAnswerSubmissionSerializer,
    AttemptFlagSubmissionSerializer,
    CBTExamSerializer,
    CBTMediaSerializer,
    CBTImportJobSerializer,
    ExamAttemptEventSerializer,
    ExamAttemptSerializer,
    ExamCandidateSerializer,
    ExamQuestionSerializer,
    ExamSectionSerializer,
    MyExamCandidateSerializer,
    QuestionBlockSerializer,
    QuestionOptionSerializer,
    QuestionSerializer,
    QuestionVersionSerializer,
    StudentAnswerSerializer,
    TopicSerializer,
)
from .services import analytics_service, attempt_service, exam_service, invigilation_service, question_service
from .services.attempt_service import AttemptError, InvalidAttemptTransition
from .services.exam_service import ExamError, InvalidExamTransition
from .services.question_service import InvalidQuestionTransition, QuestionError


class TopicListCreateView(TenantListCreateAPIView):
    serializer_class = TopicSerializer

    def get_queryset(self):
        qs = Topic.objects.filter(deleted_at__isnull=True)
        subject_id = self.request.query_params.get("subject_id")
        if subject_id:
            qs = qs.filter(subject__public_id=subject_id)
        return qs

    def get_permissions(self):
        code = "cbt_topics.create" if self.request.method == "POST" else "cbt_topics.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        serializer.save(organization=serializer.validated_data["subject"].organization)


class TopicDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = TopicSerializer

    def get_queryset(self):
        return Topic.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "cbt_topics.view", "PATCH": "cbt_topics.update", "DELETE": "cbt_topics.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        from django.utils import timezone

        instance.deleted_at = timezone.now()
        instance.save(update_fields=["deleted_at"])


class QuestionListCreateView(TenantListCreateAPIView):
    serializer_class = QuestionSerializer

    def get_queryset(self):
        qs = Question.objects.filter(deleted_at__isnull=True).prefetch_related("blocks", "options")
        subject_id = self.request.query_params.get("subject_id")
        class_level_id = self.request.query_params.get("class_level_id")
        topic_id = self.request.query_params.get("topic_id")
        status_filter = self.request.query_params.get("status")
        question_type = self.request.query_params.get("question_type")
        if subject_id:
            qs = qs.filter(subject__public_id=subject_id)
        if class_level_id:
            qs = qs.filter(class_level__public_id=class_level_id)
        if topic_id:
            qs = qs.filter(topic__public_id=topic_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if question_type:
            qs = qs.filter(question_type=question_type)
        return qs

    def get_permissions(self):
        code = "cbt_questions.create" if self.request.method == "POST" else "cbt_questions.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        serializer.save(
            organization=serializer.validated_data["subject"].organization,
            created_by=self.request.user,
            updated_by=self.request.user,
        )


class QuestionDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = QuestionSerializer

    def get_queryset(self):
        return Question.objects.filter(deleted_at__isnull=True).prefetch_related("blocks", "options")

    def get_permissions(self):
        code = {
            "GET": "cbt_questions.view",
            "PATCH": "cbt_questions.update",
            "DELETE": "cbt_questions.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        # Bypasses serializer.save() so an edit to a *published* question
        # gets its version-snapshot-first behavior (question_service.
        # update_question) rather than a plain unconditional overwrite.
        question_service.update_question(
            question=serializer.instance, actor=self.request.user, **serializer.validated_data
        )

    def perform_destroy(self, instance):
        question_service.delete_question(question=instance, actor=self.request.user)


class _QuestionTransitionView(APIView):
    transition = staticmethod(lambda *, question, actor: question)
    permission_code = "cbt_questions.update"

    def get_permissions(self):
        return [IsAuthenticated(), require_permission(self.permission_code)()]

    def post(self, request, public_id):
        question = generics.get_object_or_404(Question.objects, public_id=public_id)
        try:
            question = self.transition(question=question, actor=request.user)
        except InvalidQuestionTransition as exc:
            return error_envelope(str(exc), status=409)
        return envelope(QuestionSerializer(question).data)


class QuestionSubmitView(_QuestionTransitionView):
    transition = staticmethod(question_service.submit_question)
    permission_code = "cbt_questions.submit"


class QuestionApproveView(_QuestionTransitionView):
    transition = staticmethod(question_service.approve_question)
    permission_code = "cbt_questions.approve"


class QuestionRejectView(_QuestionTransitionView):
    transition = staticmethod(question_service.reject_question)
    permission_code = "cbt_questions.approve"


class QuestionDuplicateView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_questions.create")()]

    def post(self, request, public_id):
        question = generics.get_object_or_404(Question.objects, public_id=public_id)
        copy = question_service.duplicate_question(question=question, actor=request.user)
        return envelope(QuestionSerializer(copy).data, message="question duplicated", status=201)


class QuestionBulkImportView(APIView):
    """Import a bounded CSV or XLSX question sheet; dry-run previews never write."""

    MAX_UPLOAD_BYTES = 10 * 1024 * 1024
    MAX_ROWS = 5000
    REQUIRED_HEADERS = {"text", "correct"}

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_questions.create")()]

    def _read_rows(self, upload):
        import csv
        import io
        from pathlib import Path

        suffix = Path(upload.name or "").suffix.lower()
        raw = upload.read(self.MAX_UPLOAD_BYTES + 1)
        if len(raw) > self.MAX_UPLOAD_BYTES:
            raise ValueError("file exceeds the 10 MB import limit")

        if suffix == ".csv":
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError("CSV must use UTF-8 encoding") from exc
            reader = csv.DictReader(io.StringIO(text))
            headers = reader.fieldnames or []
            rows = list(reader)
        elif suffix == ".xlsx":
            try:
                import zipfile
                from openpyxl import load_workbook

                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    members = archive.infolist()
                    if len(members) > 1000 or sum(member.file_size for member in members) > 50 * 1024 * 1024:
                        raise ValueError("XLSX archive expands beyond the 50 MB safety limit")
                    names = {member.filename for member in members}
                    if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                        raise ValueError("file is not a valid XLSX workbook")
                workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
                try:
                    sheet = workbook.active
                    values = sheet.iter_rows(values_only=True)
                    headers = [str(value).strip().lower() if value is not None else "" for value in next(values, ())]
                    rows = []
                    for values_row in values:
                        if len(rows) >= self.MAX_ROWS:
                            raise ValueError("worksheet exceeds the 5,000 row import limit")
                        rows.append({
                            headers[index]: ("" if value is None else str(value).strip())
                            for index, value in enumerate(values_row)
                            if index < len(headers) and headers[index]
                        })
                finally:
                    workbook.close()
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError("could not read XLSX workbook; verify that it is a valid .xlsx file") from exc
        else:
            raise ValueError("only .csv and .xlsx files are supported")

        normalized = [str(header).strip().lower() if header is not None else "" for header in headers]
        if not normalized or any(not header for header in normalized):
            raise ValueError("the first row must contain non-empty column headers")
        if len(set(normalized)) != len(normalized):
            raise ValueError("column headers must be unique")
        missing = self.REQUIRED_HEADERS - set(normalized)
        if missing:
            raise ValueError(f"missing required column(s): {', '.join(sorted(missing))}")
        if len(rows) > self.MAX_ROWS:
            raise ValueError("file exceeds the 5,000 row import limit")
        return [
            {str(key).strip().lower(): ("" if value is None else str(value).strip()) for key, value in row.items()}
            for row in rows
        ]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            return error_envelope("no file provided", status=400)
        try:
            rows = self._read_rows(upload)
        except ValueError as exc:
            return error_envelope(str(exc), status=400)

        subject = generics.get_object_or_404(Subject.objects, public_id=request.data.get("subject"))
        class_level = generics.get_object_or_404(ClassLevel.objects, public_id=request.data.get("class_level"))
        if (
            subject.organization_id != request.user.organization_id
            or class_level.organization_id != request.user.organization_id
            or subject.school_id != class_level.campus.school_id
        ):
            return error_envelope("subject and class level must belong to the same school", status=400)

        dry_run_raw = request.data.get("dry_run", "false")
        dry_run = dry_run_raw is True or str(dry_run_raw).strip().lower() in {"1", "true", "yes"}
        result = question_service.bulk_import_questions(
            organization=request.user.organization,
            actor=request.user,
            subject=subject,
            class_level=class_level,
            rows=rows,
            dry_run=dry_run,
        )
        data = {
            "created": QuestionSerializer(result["created"], many=True).data,
            "preview": result["preview"],
            "errors": result["errors"],
            "created_count": len(result["created"]),
            "valid_count": len(result["preview"]) if dry_run else len(result["created"]),
            "error_count": len(result["errors"]),
            "dry_run": dry_run,
        }
        return envelope(
            data,
            message="question import preview completed" if dry_run else "bulk import completed",
            status=200 if dry_run or not result["created"] else 201,
        )


class QuestionVersionListView(TenantListAPIView):
    """GET only — versions are written exclusively by question_service on
    edit-after-publish, never created directly by a client."""

    serializer_class = QuestionVersionSerializer

    def get_queryset(self):
        return QuestionVersion.objects.filter(question__public_id=self.kwargs["public_id"])

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_questions.view")()]


class QuestionBlockListCreateView(TenantListCreateAPIView):
    serializer_class = QuestionBlockSerializer

    def get_question(self) -> Question:
        return generics.get_object_or_404(Question.objects, public_id=self.kwargs["public_id"])

    def get_queryset(self):
        return QuestionBlock.objects.filter(question__public_id=self.kwargs["public_id"])

    def get_permissions(self):
        code = "cbt_questions.update" if self.request.method == "POST" else "cbt_questions.view"
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except QuestionError as exc:
            return error_envelope(str(exc), status=400)

    def perform_create(self, serializer):
        question = self.get_question()
        question_service.validate_block_content(
            block_type=serializer.validated_data["block_type"],
            content=serializer.validated_data.get("content", {}),
        )
        serializer.save(organization=question.organization, question=question)


class QuestionBlockDetailView(TenantRetrieveUpdateDestroyAPIView):
    http_method_names = ["patch", "delete"]
    serializer_class = QuestionBlockSerializer
    lookup_url_kwarg = "block_public_id"

    def get_queryset(self):
        return QuestionBlock.objects.filter(question__public_id=self.kwargs["public_id"])

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_questions.update")()]

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except QuestionError as exc:
            return error_envelope(str(exc), status=400)

    def perform_update(self, serializer):
        block_type = serializer.validated_data.get("block_type", serializer.instance.block_type)
        content = serializer.validated_data.get("content", serializer.instance.content)
        question_service.validate_block_content(block_type=block_type, content=content)
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()


class QuestionOptionListCreateView(TenantListCreateAPIView):
    serializer_class = QuestionOptionSerializer

    def get_question(self) -> Question:
        return generics.get_object_or_404(Question.objects, public_id=self.kwargs["public_id"])

    def get_queryset(self):
        return QuestionOption.objects.filter(question__public_id=self.kwargs["public_id"])

    def get_permissions(self):
        code = "cbt_questions.update" if self.request.method == "POST" else "cbt_questions.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        question = self.get_question()
        serializer.save(organization=question.organization, question=question)


class QuestionOptionDetailView(TenantRetrieveUpdateDestroyAPIView):
    http_method_names = ["patch", "delete"]
    serializer_class = QuestionOptionSerializer
    lookup_url_kwarg = "option_public_id"

    def get_queryset(self):
        return QuestionOption.objects.filter(question__public_id=self.kwargs["public_id"])

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_questions.update")()]

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()


class CBTMediaListView(TenantListAPIView):
    """Metadata list only — uploads go through CBTMediaUploadView
    (multipart, not JSON), matching how apps.examinations.QuestionImageView
    keeps uploads out of a plain ModelSerializer.
    """

    serializer_class = CBTMediaSerializer

    def get_queryset(self):
        qs = CBTMedia.objects.filter(deleted_at__isnull=True)
        media_type = self.request.query_params.get("media_type")
        if media_type:
            qs = qs.filter(media_type=media_type)
        return qs

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_media.view")()]


class CBTMediaUploadView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_media.upload")()]

    def post(self, request):
        from apps.core.storage import InvalidUpload

        upload = request.FILES.get("file")
        if upload is None:
            return error_envelope("no file provided", status=400)
        try:
            media = question_service.upload_media(
                organization=request.user.organization,
                actor=request.user,
                name=request.data.get("name") or upload.name,
                media_type=request.data.get("media_type", "image"),
                file_name=upload.name,
                content=upload.read(),
                content_type=upload.content_type,
            )
        except InvalidUpload as exc:
            return error_envelope(str(exc), status=400)
        return envelope(CBTMediaSerializer(media).data, message="media uploaded", status=201)


class CBTMediaDetailView(TenantRetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "delete"]
    serializer_class = CBTMediaSerializer

    def get_queryset(self):
        return CBTMedia.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = "cbt_media.view" if self.request.method == "GET" else "cbt_media.delete"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_destroy(self, instance):
        from django.utils import timezone

        instance.deleted_at = timezone.now()
        instance.updated_by = self.request.user
        instance.save(update_fields=["deleted_at", "updated_by", "updated_at"])


class CBTExamListCreateView(TenantListCreateAPIView):
    serializer_class = CBTExamSerializer

    def get_queryset(self):
        qs = CBTExam.objects.filter(deleted_at__isnull=True)
        subject_id = self.request.query_params.get("subject_id")
        class_level_id = self.request.query_params.get("class_level_id")
        term_id = self.request.query_params.get("term_id")
        status_filter = self.request.query_params.get("status")
        exam_type = self.request.query_params.get("exam_type")
        if subject_id:
            qs = qs.filter(subject__public_id=subject_id)
        if class_level_id:
            qs = qs.filter(class_level__public_id=class_level_id)
        if term_id:
            qs = qs.filter(term__public_id=term_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        if exam_type:
            qs = qs.filter(exam_type=exam_type)
        return qs

    def get_permissions(self):
        code = "cbt_exams.create" if self.request.method == "POST" else "cbt_exams.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        serializer.save(
            organization=serializer.validated_data["school"].organization,
            created_by=self.request.user,
            updated_by=self.request.user,
        )


class CBTExamDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = CBTExamSerializer

    def get_queryset(self):
        return CBTExam.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "cbt_exams.view",
            "PATCH": "cbt_exams.update",
            "DELETE": "cbt_exams.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except ExamError as exc:
            return error_envelope(str(exc), status=409)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ExamError as exc:
            return error_envelope(str(exc), status=409)

    def perform_update(self, serializer):
        exam_service.update_exam(exam=serializer.instance, actor=self.request.user, **serializer.validated_data)

    def perform_destroy(self, instance):
        exam_service.delete_exam(exam=instance, actor=self.request.user)


class _ExamTransitionView(APIView):
    transition = staticmethod(lambda *, exam, actor: exam)
    permission_code = "cbt_exams.publish"

    def get_permissions(self):
        return [IsAuthenticated(), require_permission(self.permission_code)()]

    def post(self, request, public_id):
        exam = generics.get_object_or_404(CBTExam.objects, public_id=public_id)
        try:
            exam = self.transition(exam=exam, actor=request.user)
        except InvalidExamTransition as exc:
            return error_envelope(str(exc), status=409)
        except ExamError as exc:
            return error_envelope(str(exc), status=400)
        return envelope(CBTExamSerializer(exam).data)


class CBTExamPublishView(_ExamTransitionView):
    transition = staticmethod(exam_service.publish_exam)


class CBTExamArchiveView(_ExamTransitionView):
    transition = staticmethod(exam_service.archive_exam)


class ExamGenerateQuestionsView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_exams.update")()]

    def post(self, request, public_id):
        exam = generics.get_object_or_404(CBTExam.objects, public_id=public_id)
        subject = generics.get_object_or_404(Subject.objects, public_id=request.data["subject"])
        class_level = generics.get_object_or_404(ClassLevel.objects, public_id=request.data["class_level"])
        topic = None
        if request.data.get("topic"):
            topic = generics.get_object_or_404(Topic.objects, public_id=request.data["topic"])
        try:
            created = exam_service.generate_questions_for_exam(
                exam=exam,
                subject=subject,
                class_level=class_level,
                topic=topic,
                count=int(request.data["count"]),
                difficulty_distribution=request.data.get("difficulty_distribution"),
                question_types=request.data.get("question_types"),
            )
        except ExamError as exc:
            return error_envelope(str(exc), status=400)
        return envelope(
            ExamQuestionSerializer(created, many=True).data, message="questions generated", status=201
        )


class ExamAnalyticsView(APIView):
    """Staff-facing: exam-wide summary stats plus per-question item
    analysis (facility/discrimination index), computed only over
    finalized attempts — see analytics_service's module docstring. Gated
    on the same permission as viewing the exam itself: this is a read-only
    report about an exam a caller can already see, not a distinct
    capability worth its own permission code.
    """

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_exams.view")()]

    def get(self, request, public_id):
        exam = generics.get_object_or_404(CBTExam.objects, public_id=public_id)
        return envelope(
            {
                "summary": analytics_service.exam_summary(exam=exam),
                "items": analytics_service.item_analysis(exam=exam),
            }
        )


class ExamLiveStatusView(APIView):
    """Staff-facing: poll-based live status of every candidate during an
    exam window — who's started, time remaining, progress, and whether
    they're flagged. Gated on cbt_attempts.view, the same permission as
    the staff attempt list/detail endpoints, since this is the same
    attempt data at a different granularity (a live snapshot rather than
    a historical record).
    """

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_attempts.view")()]

    def get(self, request, public_id):
        from django.utils import timezone

        exam = generics.get_object_or_404(CBTExam.objects, public_id=public_id)
        return envelope(
            {
                "server_time": timezone.now(),
                "candidates": invigilation_service.live_status(exam=exam),
            }
        )


class ExamSectionListCreateView(TenantListCreateAPIView):
    serializer_class = ExamSectionSerializer

    def get_exam(self) -> CBTExam:
        return generics.get_object_or_404(CBTExam.objects, public_id=self.kwargs["public_id"])

    def get_queryset(self):
        return ExamSection.objects.filter(exam__public_id=self.kwargs["public_id"])

    def get_permissions(self):
        code = "cbt_exams.update" if self.request.method == "POST" else "cbt_exams.view"
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except ExamError as exc:
            return error_envelope(str(exc), status=409)

    def perform_create(self, serializer):
        exam = self.get_exam()
        instance = exam_service.add_section(exam=exam, **serializer.validated_data)
        serializer.instance = instance


class ExamSectionDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = ExamSectionSerializer
    lookup_url_kwarg = "section_public_id"

    def get_queryset(self):
        return ExamSection.objects.filter(exam__public_id=self.kwargs["public_id"])

    def get_permissions(self):
        code = "cbt_exams.update" if self.request.method in ("PATCH", "DELETE") else "cbt_exams.view"
        return [IsAuthenticated(), require_permission(code)()]

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except ExamError as exc:
            return error_envelope(str(exc), status=409)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ExamError as exc:
            return error_envelope(str(exc), status=409)

    def perform_update(self, serializer):
        exam_service.update_section(section=serializer.instance, **serializer.validated_data)

    def perform_destroy(self, instance):
        exam_service.remove_section(section=instance)


class ExamQuestionListCreateView(TenantListCreateAPIView):
    serializer_class = ExamQuestionSerializer

    def get_exam(self) -> CBTExam:
        return generics.get_object_or_404(CBTExam.objects, public_id=self.kwargs["public_id"])

    def get_queryset(self):
        return ExamQuestion.objects.filter(exam__public_id=self.kwargs["public_id"]).select_related("question")

    def get_permissions(self):
        code = "cbt_exams.update" if self.request.method == "POST" else "cbt_exams.view"
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except ExamError as exc:
            return error_envelope(str(exc), status=409)

    def perform_create(self, serializer):
        exam = self.get_exam()
        instance = exam_service.add_question_to_exam(exam=exam, **serializer.validated_data)
        serializer.instance = instance


class ExamQuestionDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = ExamQuestionSerializer
    lookup_url_kwarg = "exam_question_public_id"

    def get_queryset(self):
        return ExamQuestion.objects.filter(exam__public_id=self.kwargs["public_id"]).select_related("question")

    def get_permissions(self):
        code = "cbt_exams.update" if self.request.method in ("PATCH", "DELETE") else "cbt_exams.view"
        return [IsAuthenticated(), require_permission(code)()]

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except ExamError as exc:
            return error_envelope(str(exc), status=409)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ExamError as exc:
            return error_envelope(str(exc), status=409)

    def perform_update(self, serializer):
        exam_service.update_exam_question(exam_question=serializer.instance, **serializer.validated_data)

    def perform_destroy(self, instance):
        exam_service.remove_question_from_exam(exam_question=instance)


class ExamQuestionReorderView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_exams.update")()]

    def post(self, request, public_id):
        exam = generics.get_object_or_404(CBTExam.objects, public_id=public_id)
        try:
            exam_service.reorder_exam_questions(
                exam=exam, ordered_public_ids=request.data.get("ordered_public_ids", [])
            )
        except ExamError as exc:
            return error_envelope(str(exc), status=409)
        serializer = ExamQuestionSerializer(exam.exam_questions.select_related("question"), many=True)
        return envelope(serializer.data)


class ExamCandidateListCreateView(TenantListCreateAPIView):
    serializer_class = ExamCandidateSerializer

    def get_exam(self) -> CBTExam:
        return generics.get_object_or_404(CBTExam.objects, public_id=self.kwargs["public_id"])

    def get_queryset(self):
        return ExamCandidate.objects.filter(exam__public_id=self.kwargs["public_id"]).select_related("student")

    def get_permissions(self):
        code = "cbt_exam_candidates.manage" if self.request.method == "POST" else "cbt_exam_candidates.view"
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except ExamError as exc:
            return error_envelope(str(exc), status=409)

    def perform_create(self, serializer):
        exam = self.get_exam()
        instance = exam_service.add_candidate(exam=exam, student=serializer.validated_data["student"])
        serializer.instance = instance


class ExamCandidateDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = ExamCandidateSerializer
    lookup_url_kwarg = "candidate_public_id"

    def get_queryset(self):
        return ExamCandidate.objects.filter(exam__public_id=self.kwargs["public_id"]).select_related("student")

    def get_permissions(self):
        code = "cbt_exam_candidates.manage" if self.request.method in ("PATCH", "DELETE") else "cbt_exam_candidates.view"
        return [IsAuthenticated(), require_permission(code)()]

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except ExamError as exc:
            return error_envelope(str(exc), status=409)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ExamError as exc:
            return error_envelope(str(exc), status=409)

    def perform_update(self, serializer):
        exam_service.update_candidate(candidate=serializer.instance, **serializer.validated_data)

    def perform_destroy(self, instance):
        exam_service.remove_candidate(candidate=instance)


class ExamCandidateBulkFromClassArmView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_exam_candidates.manage")()]

    def post(self, request, public_id):
        from apps.academics.models import ClassArm
        from apps.schools.models import AcademicYear

        exam = generics.get_object_or_404(CBTExam.objects, public_id=public_id)
        class_arm = generics.get_object_or_404(ClassArm.objects, public_id=request.data["class_arm"])
        academic_year = generics.get_object_or_404(AcademicYear.objects, public_id=request.data["academic_year"])
        try:
            candidates = exam_service.add_candidates_from_class_arm(
                exam=exam, class_arm=class_arm, academic_year=academic_year
            )
        except ExamError as exc:
            return error_envelope(str(exc), status=409)
        return envelope(
            ExamCandidateSerializer(candidates, many=True).data, message="candidates added", status=201
        )


def _attempt_payload(attempt: ExamAttempt) -> dict:
    return {
        "attempt": ExamAttemptSerializer(attempt).data,
        "questions": attempt_service.build_delivery_payload(attempt=attempt),
    }


def _own_attempt_or_error(request, public_id):
    """start/heartbeat/save-answer/flag/submit are ownership-gated, not
    RBAC-gated (see attempt_service module docstring's design note): every
    student must always be able to act on their own attempt regardless of
    what permissions any role happens to grant. Returns (attempt, None) on
    success, or (None, error_response) — an ownership failure is reported
    as a 404, not a 403, so a candidate can't probe for other students'
    attempt IDs by distinguishing "forbidden" from "not found".
    """
    student = getattr(request.user, "student_profile", None)
    if student is None:
        return None, error_envelope("no student profile is linked to this account", status=404)
    attempt = generics.get_object_or_404(
        ExamAttempt.objects.select_related("exam", "candidate"), public_id=public_id, candidate__student=student
    )
    return attempt, None


class MyCandidateListView(TenantListAPIView):
    """Self-service: which CBT exams am I a candidate for. Ownership-
    scoped, not RBAC-gated, like every other cbt/my/... endpoint — only
    the student themselves should ever see their own candidacies. A
    caller with no student profile (staff/admin/guardian) gets an empty
    list rather than an error, matching apps.dashboards' own self-service
    "my-..." endpoints.
    """

    serializer_class = MyExamCandidateSerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        student = getattr(self.request.user, "student_profile", None)
        if student is None:
            return ExamCandidate.objects.none()
        return ExamCandidate.objects.filter(student=student).select_related("exam__subject", "attempt")


class AttemptStartView(APIView):
    """Self-service: a student starts (or resumes) their own attempt at an
    exam they're a candidate for — see start_attempt's idempotent resume
    behavior."""

    permission_classes = [IsAuthenticated]

    def post(self, request, candidate_public_id):
        student = getattr(request.user, "student_profile", None)
        if student is None:
            return error_envelope("no student profile is linked to this account", status=404)
        candidate = generics.get_object_or_404(ExamCandidate.objects, public_id=candidate_public_id, student=student)
        try:
            attempt = attempt_service.start_attempt(
                candidate=candidate,
                ip_address=request.META.get("REMOTE_ADDR", ""),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except AttemptError as exc:
            return error_envelope(str(exc), status=400)
        return envelope(_attempt_payload(attempt))


class AttemptDetailView(APIView):
    """Self-service: fetch the candidate's own attempt plus its
    answer-key-stripped question content — what a client needs to render
    or resume the exam."""

    permission_classes = [IsAuthenticated]

    def get(self, request, public_id):
        attempt, err = _own_attempt_or_error(request, public_id)
        if err:
            return err
        return envelope(_attempt_payload(attempt))


class AttemptHeartbeatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):
        attempt, err = _own_attempt_or_error(request, public_id)
        if err:
            return err
        attempt = attempt_service.heartbeat(attempt=attempt)
        return envelope(_attempt_payload(attempt))


class AttemptAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):
        attempt, err = _own_attempt_or_error(request, public_id)
        if err:
            return err
        serializer = AttemptAnswerSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exam_question = generics.get_object_or_404(
            ExamQuestion.objects,
            public_id=serializer.validated_data["exam_question"],
            exam=attempt.exam,
        )
        try:
            answer = attempt_service.save_answer(
                attempt=attempt,
                exam_question=exam_question,
                response=serializer.validated_data["response"],
                time_spent_seconds=serializer.validated_data["time_spent_seconds"],
            )
        except AttemptError as exc:
            return error_envelope(str(exc), status=400)
        return envelope(StudentAnswerSerializer(answer).data)


class AttemptFlagView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):
        attempt, err = _own_attempt_or_error(request, public_id)
        if err:
            return err
        serializer = AttemptFlagSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exam_question = generics.get_object_or_404(
            ExamQuestion.objects,
            public_id=serializer.validated_data["exam_question"],
            exam=attempt.exam,
        )
        try:
            answer = attempt_service.set_flag(
                attempt=attempt,
                exam_question=exam_question,
                flagged=serializer.validated_data["flagged"],
            )
        except AttemptError as exc:
            return error_envelope(str(exc), status=400)
        return envelope(StudentAnswerSerializer(answer).data)


class AttemptEventView(APIView):
    """Self-service: the client reports one proctoring signal (tab hidden,
    fullscreen exit, copy/paste, connectivity change, ...) as it happens
    during the attempt. See attempt_service.log_attempt_event for which of
    these count toward auto-flagging the attempt for a human reviewer.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):
        attempt, err = _own_attempt_or_error(request, public_id)
        if err:
            return err
        serializer = ExamAttemptEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            event = attempt_service.log_attempt_event(
                attempt=attempt,
                event_type=serializer.validated_data["event_type"],
                metadata=serializer.validated_data.get("metadata", {}),
                client_event_id=serializer.validated_data.get("client_event_id"),
            )
        except AttemptError as exc:
            return error_envelope(str(exc), status=400)
        status_code = 201 if getattr(event, "_was_created", True) else 200
        return envelope(ExamAttemptEventSerializer(event).data, status=status_code)


class AttemptSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):
        attempt, err = _own_attempt_or_error(request, public_id)
        if err:
            return err
        try:
            attempt = attempt_service.submit_attempt(attempt=attempt, actor=request.user)
        except InvalidAttemptTransition as exc:
            return error_envelope(str(exc), status=409)
        except AttemptError as exc:
            # e.g. finalize_attempt's Result-integration step failed — the
            # submission and scoring themselves already committed (see
            # submit_attempt's docstring on why it isn't one atomic block
            # with finalize_attempt), so this is reported but not fatal to
            # the candidate's already-recorded work.
            return error_envelope(str(exc), status=422)
        return envelope(_attempt_payload(attempt))


class ExamAttemptListView(TenantListAPIView):
    """Staff-facing: every candidate's attempt at one exam — RBAC-gated,
    org-wide, no ownership narrowing (that's the self-service views above).
    """

    serializer_class = ExamAttemptSerializer

    def get_queryset(self):
        qs = ExamAttempt.objects.filter(exam__public_id=self.kwargs["public_id"]).select_related(
            "candidate__student", "exam"
        )
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        flagged_param = self.request.query_params.get("flagged_for_review")
        if flagged_param is not None:
            qs = qs.filter(flagged_for_review=flagged_param.lower() in ("1", "true", "yes"))
        return qs

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_attempts.view")()]


class ExamAttemptDetailView(APIView):
    """Staff-facing: one attempt plus its answers and proctoring events,
    for review/grading."""

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_attempts.view")()]

    def get(self, request, public_id, attempt_public_id):
        attempt = generics.get_object_or_404(
            ExamAttempt.objects.filter(exam__public_id=public_id).select_related("candidate__student", "exam"),
            public_id=attempt_public_id,
        )
        answers = attempt.answers.select_related("exam_question")
        return envelope(
            {
                "attempt": ExamAttemptSerializer(attempt).data,
                "answers": StudentAnswerSerializer(answers, many=True).data,
                "events": ExamAttemptEventSerializer(attempt.events.all(), many=True).data,
            }
        )


class StudentAnswerGradeView(APIView):
    """Staff-facing: manually award marks to one subjective StudentAnswer —
    the only write path for a question type scoring_service can't
    auto-grade (see attempt_service.grade_subjective_answer)."""

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_attempts.grade")()]

    def post(self, request, public_id):
        answer = generics.get_object_or_404(StudentAnswer.objects, public_id=public_id)
        try:
            marks_awarded = Decimal(str(request.data["marks_awarded"]))
        except (KeyError, InvalidOperation, TypeError):
            return error_envelope("marks_awarded is required and must be a number", status=400)
        try:
            answer = attempt_service.grade_subjective_answer(
                student_answer=answer, marks_awarded=marks_awarded, actor=request.user
            )
        except AttemptError as exc:
            return error_envelope(str(exc), status=400)
        return envelope(StudentAnswerSerializer(answer).data)


class CBTImportJobListCreateView(APIView):
    """Create durable source-import jobs and list the caller's tenant jobs.

    Uploads are validated and stored privately. No Celery task is dispatched
    until the dedicated production imports worker has been deployed/verified.
    """

    def get_permissions(self):
        code = "cbt_questions.create" if self.request.method == "POST" else "cbt_questions.view"
        return [IsAuthenticated(), require_permission(code)()]

    def get(self, request):
        jobs = (
            CBTImportJob.objects.select_related("school", "subject", "class_level")
            .order_by("-created_at")[:100]
        )
        return envelope(CBTImportJobSerializer(jobs, many=True).data)

    def post(self, request):
        from .services.source_upload_service import (
            ImportIdempotencyConflict,
            InvalidSourceUpload,
            create_source_import_job,
            validate_source_upload,
        )

        upload = request.FILES.get("file")
        if upload is None:
            return error_envelope("no file provided", status=400)

        subject_id = request.data.get("subject")
        class_level_id = request.data.get("class_level")
        if not subject_id or not class_level_id:
            return error_envelope("subject and class_level are required", status=400)

        subject = generics.get_object_or_404(Subject.objects, public_id=subject_id)
        class_level = generics.get_object_or_404(ClassLevel.objects, public_id=class_level_id)
        school = class_level.campus.school
        if (
            subject.organization_id != request.user.organization_id
            or class_level.organization_id != request.user.organization_id
            or subject.school_id != school.pk
        ):
            return error_envelope("subject and class level must belong to the same school", status=400)

        try:
            source = validate_source_upload(upload)
            job, created = create_source_import_job(
                organization=request.user.organization,
                actor=request.user,
                school=school,
                subject=subject,
                class_level=class_level,
                source=source,
                idempotency_key=request.headers.get("Idempotency-Key", ""),
            )
        except InvalidSourceUpload as exc:
            return error_envelope(str(exc), status=400)
        except ImportIdempotencyConflict as exc:
            return error_envelope(str(exc), status=409)

        data = CBTImportJobSerializer(job).data
        data["processing_status"] = "not_configured"
        data["processing_dispatched"] = False
        return envelope(
            data,
            message=(
                "source stored; processing is not configured until the imports worker is deployed"
                if created else "existing import job returned for this idempotency key"
            ),
            status=201 if created else 200,
        )


class CBTImportJobDetailView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("cbt_questions.view")()]

    def get(self, request, public_id):
        job = generics.get_object_or_404(
            CBTImportJob.objects.select_related("school", "subject", "class_level"),
            public_id=public_id,
        )
        data = CBTImportJobSerializer(job).data
        data["processing_status"] = "not_configured" if job.status == "uploaded" else "managed"
        data["processing_dispatched"] = False
        return envelope(data)
