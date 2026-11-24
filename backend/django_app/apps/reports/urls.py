from django.urls import path

from .views import ReportRequestDetailView, ReportRequestDownloadView, ReportRequestListCreateView

urlpatterns = [
    path("reports", ReportRequestListCreateView.as_view(), name="report-request-list-create"),
    path("reports/<uuid:public_id>", ReportRequestDetailView.as_view(), name="report-request-detail"),
    path(
        "reports/<uuid:public_id>/download",
        ReportRequestDownloadView.as_view(),
        name="report-request-download",
    ),
]
