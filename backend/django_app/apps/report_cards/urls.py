from django.urls import path

from .views import (
    ReportCardDetailView,
    ReportCardGenerateBulkView,
    ReportCardGenerateView,
    ReportCardListView,
    ReportCardPdfView,
    ReportCardPublishView,
    ReportCardRegenerateView,
    ReportCardUnpublishView,
    ReportCardWeightingDetailView,
    ReportCardWeightingListCreateView,
)

urlpatterns = [
    path(
        "report-card-weightings",
        ReportCardWeightingListCreateView.as_view(),
        name="report-card-weighting-list-create",
    ),
    path(
        "report-card-weightings/<uuid:public_id>",
        ReportCardWeightingDetailView.as_view(),
        name="report-card-weighting-detail",
    ),
    path("report-cards", ReportCardListView.as_view(), name="report-card-list"),
    path("report-cards/generate", ReportCardGenerateView.as_view(), name="report-card-generate"),
    path(
        "report-cards/generate-bulk",
        ReportCardGenerateBulkView.as_view(),
        name="report-card-generate-bulk",
    ),
    path("report-cards/<uuid:public_id>", ReportCardDetailView.as_view(), name="report-card-detail"),
    path(
        "report-cards/<uuid:public_id>/regenerate",
        ReportCardRegenerateView.as_view(),
        name="report-card-regenerate",
    ),
    path(
        "report-cards/<uuid:public_id>/publish",
        ReportCardPublishView.as_view(),
        name="report-card-publish",
    ),
    path(
        "report-cards/<uuid:public_id>/unpublish",
        ReportCardUnpublishView.as_view(),
        name="report-card-unpublish",
    ),
    path("report-cards/<uuid:public_id>/pdf", ReportCardPdfView.as_view(), name="report-card-pdf"),
]
