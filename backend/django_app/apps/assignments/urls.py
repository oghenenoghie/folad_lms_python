from django.urls import path

from .views import (
    AssignmentDetailView,
    AssignmentListCreateView,
    AssignmentSubmissionDetailView,
    AssignmentSubmissionDownloadView,
    AssignmentSubmissionGradeView,
    AssignmentSubmissionListCreateView,
    AssignmentSubmissionUploadView,
)

urlpatterns = [
    path("assignments", AssignmentListCreateView.as_view(), name="assignment-list-create"),
    path("assignments/<uuid:public_id>", AssignmentDetailView.as_view(), name="assignment-detail"),
    path(
        "assignment-submissions",
        AssignmentSubmissionListCreateView.as_view(),
        name="assignment-submission-list-create",
    ),
    path(
        "assignment-submissions/upload",
        AssignmentSubmissionUploadView.as_view(),
        name="assignment-submission-upload",
    ),
    path(
        "assignment-submissions/<uuid:public_id>",
        AssignmentSubmissionDetailView.as_view(),
        name="assignment-submission-detail",
    ),
    path(
        "assignment-submissions/<uuid:public_id>/download",
        AssignmentSubmissionDownloadView.as_view(),
        name="assignment-submission-download",
    ),
    path(
        "assignment-submissions/<uuid:public_id>/grade",
        AssignmentSubmissionGradeView.as_view(),
        name="assignment-submission-grade",
    ),
]
