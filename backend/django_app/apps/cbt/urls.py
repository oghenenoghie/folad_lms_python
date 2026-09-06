from django.urls import path

from .views import (
    CBTMediaDetailView,
    CBTMediaListView,
    CBTMediaUploadView,
    QuestionApproveView,
    QuestionBlockDetailView,
    QuestionBlockListCreateView,
    QuestionDetailView,
    QuestionDuplicateView,
    QuestionListCreateView,
    QuestionOptionDetailView,
    QuestionOptionListCreateView,
    QuestionRejectView,
    QuestionSubmitView,
    QuestionVersionListView,
    TopicDetailView,
    TopicListCreateView,
)

urlpatterns = [
    path("cbt/topics", TopicListCreateView.as_view(), name="cbt-topic-list-create"),
    path("cbt/topics/<uuid:public_id>", TopicDetailView.as_view(), name="cbt-topic-detail"),
    path("cbt/questions", QuestionListCreateView.as_view(), name="cbt-question-list-create"),
    path("cbt/questions/<uuid:public_id>", QuestionDetailView.as_view(), name="cbt-question-detail"),
    path("cbt/questions/<uuid:public_id>/submit", QuestionSubmitView.as_view(), name="cbt-question-submit"),
    path("cbt/questions/<uuid:public_id>/approve", QuestionApproveView.as_view(), name="cbt-question-approve"),
    path("cbt/questions/<uuid:public_id>/reject", QuestionRejectView.as_view(), name="cbt-question-reject"),
    path(
        "cbt/questions/<uuid:public_id>/duplicate",
        QuestionDuplicateView.as_view(),
        name="cbt-question-duplicate",
    ),
    path(
        "cbt/questions/<uuid:public_id>/versions",
        QuestionVersionListView.as_view(),
        name="cbt-question-version-list",
    ),
    path(
        "cbt/questions/<uuid:public_id>/blocks",
        QuestionBlockListCreateView.as_view(),
        name="cbt-question-block-list-create",
    ),
    path(
        "cbt/questions/<uuid:public_id>/blocks/<uuid:block_public_id>",
        QuestionBlockDetailView.as_view(),
        name="cbt-question-block-detail",
    ),
    path(
        "cbt/questions/<uuid:public_id>/options",
        QuestionOptionListCreateView.as_view(),
        name="cbt-question-option-list-create",
    ),
    path(
        "cbt/questions/<uuid:public_id>/options/<uuid:option_public_id>",
        QuestionOptionDetailView.as_view(),
        name="cbt-question-option-detail",
    ),
    path("cbt/media", CBTMediaListView.as_view(), name="cbt-media-list"),
    path("cbt/media/upload", CBTMediaUploadView.as_view(), name="cbt-media-upload"),
    path("cbt/media/<uuid:public_id>", CBTMediaDetailView.as_view(), name="cbt-media-detail"),
]
