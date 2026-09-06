"""Thin views, fat services (§11 ARCHITECTURE.md) — same convention as
apps.examinations/apps.report_cards. QuestionBlock/QuestionOption are
nested under their Question in the URL (they're pure sub-resources of a
question's content, not independently permissioned or listed) rather than
top-level endpoints the way apps.examinations.QuestionOption is — see the
CBT spec's own API section for why nesting is the right call here.
"""
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import (
    TenantListAPIView,
    TenantListCreateAPIView,
    TenantRetrieveUpdateDestroyAPIView,
)
from apps.core.responses import envelope, error_envelope

from .models import CBTMedia, Question, QuestionBlock, QuestionOption, QuestionVersion, Topic
from .serializers import (
    CBTMediaSerializer,
    QuestionBlockSerializer,
    QuestionOptionSerializer,
    QuestionSerializer,
    QuestionVersionSerializer,
    TopicSerializer,
)
from .services import question_service
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
