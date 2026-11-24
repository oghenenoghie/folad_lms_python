"""Thin views, fat services (§11 ARCHITECTURE.md). Create + read-only plus a
dedicated download endpoint — same shape as apps.examinations' ReportCard
and apps.finance's Receipt. Download computes a fresh presigned URL at
request time, after the same auth + tenant-scoped get_queryset() check
every other detail view goes through.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveAPIView
from apps.core.responses import envelope, error_envelope

from .models import ReportRequest
from .serializers import ReportRequestSerializer
from .services import report_service


class ReportRequestListCreateView(TenantListCreateAPIView):
    serializer_class = ReportRequestSerializer

    def get_queryset(self):
        qs = ReportRequest.objects.filter(deleted_at__isnull=True)
        report_type = self.request.query_params.get("report_type")
        school_id = self.request.query_params.get("school_id")
        if report_type:
            qs = qs.filter(report_type=report_type)
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "reports.create" if self.request.method == "POST" else "reports.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = report_service.request_report(school=school, actor=self.request.user, **data)


class ReportRequestDetailView(TenantRetrieveAPIView):
    serializer_class = ReportRequestSerializer

    def get_queryset(self):
        return ReportRequest.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("reports.view")()]


class ReportRequestDownloadView(APIView):
    permission_classes = [IsAuthenticated, require_permission("reports.view")]

    def get(self, request, public_id):
        try:
            report_request = ReportRequest.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except ReportRequest.DoesNotExist:
            return error_envelope("report request not found", status=404)
        url = report_service.get_download_url(report_request)
        if url is None:
            return error_envelope("report is not ready yet", status=404)
        return envelope({"url": url})
