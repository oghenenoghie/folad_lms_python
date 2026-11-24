from django.urls import path

from .views import (
    ReportCardAuditListView,
    ReportCardBulkExportDetailView,
    ReportCardBulkExportDownloadView,
    ReportCardBulkExportListView,
    ReportCardBulkExportRequestView,
    ReportCardDetailView,
    ReportCardGenerateBulkView,
    ReportCardGenerateView,
    ReportCardListView,
    ReportCardPdfView,
    ReportCardPublishView,
    ReportCardRegenerateView,
    ReportCardUnpublishView,
    ReportCardVerifyView,
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
    path(
        "report-cards/verify/<str:verification_code>",
        ReportCardVerifyView.as_view(),
        name="report-card-verify",
    ),
    path("report-cards/audit", ReportCardAuditListView.as_view(), name="report-card-audit-list"),
    path(
        "report-cards/bulk-exports",
        ReportCardBulkExportListView.as_view(),
        name="report-card-bulk-export-list",
    ),
    path(
        "report-cards/bulk-exports/request",
        ReportCardBulkExportRequestView.as_view(),
        name="report-card-bulk-export-request",
    ),
    path(
        "report-cards/bulk-exports/<uuid:public_id>",
        ReportCardBulkExportDetailView.as_view(),
        name="report-card-bulk-export-detail",
    ),
    path(
        "report-cards/bulk-exports/<uuid:public_id>/download",
        ReportCardBulkExportDownloadView.as_view(),
        name="report-card-bulk-export-download",
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
