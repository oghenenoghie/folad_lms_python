"""Thin views, fat services (§11 ARCHITECTURE.md) — same convention as
apps.examinations. ReportCard has no client-facing create/update/delete
via the generic CRUD verbs: it's only ever produced by generate/
generate-bulk and transitioned by publish/unpublish, mirroring how
apps.examinations.Result's workflow transitions are dedicated APIView
endpoints rather than a generic PATCH.
"""
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import (
    TenantListAPIView,
    TenantListCreateAPIView,
    TenantRetrieveUpdateDestroyAPIView,
)
from apps.core.responses import envelope, error_envelope

from .models import PsychomotorTrait, ReportCard, ReportCardAudit, ReportCardBulkExport, ReportCardWeighting
from .serializers import (
    PsychomotorTraitSerializer,
    ReportCardAuditSerializer,
    ReportCardBulkExportRequestSerializer,
    ReportCardBulkExportSerializer,
    ReportCardGenerateBulkSerializer,
    ReportCardGenerateSerializer,
    ReportCardSerializer,
    ReportCardVerifySerializer,
    ReportCardWeightingSerializer,
)
from .services import report_card_bulk_export_service, report_card_service
from .services.report_card_service import InvalidReportCardTransition, ReportCardError


class ReportCardWeightingListCreateView(TenantListCreateAPIView):
    serializer_class = ReportCardWeightingSerializer

    def get_queryset(self):
        qs = ReportCardWeighting.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = (
            "report_card_weightings.create"
            if self.request.method == "POST"
            else "report_card_weightings.view"
        )
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        serializer.save(organization=serializer.validated_data["school"].organization)


class ReportCardWeightingDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = ReportCardWeightingSerializer

    def get_queryset(self):
        return ReportCardWeighting.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "report_card_weightings.view",
            "PATCH": "report_card_weightings.update",
            "DELETE": "report_card_weightings.update",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]


class PsychomotorTraitListCreateView(TenantListCreateAPIView):
    serializer_class = PsychomotorTraitSerializer

    def get_queryset(self):
        qs = PsychomotorTrait.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "psychomotor_traits.create" if self.request.method == "POST" else "psychomotor_traits.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        serializer.save(organization=serializer.validated_data["school"].organization)


class PsychomotorTraitDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = PsychomotorTraitSerializer

    def get_queryset(self):
        return PsychomotorTrait.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "psychomotor_traits.view",
            "PATCH": "psychomotor_traits.update",
            "DELETE": "psychomotor_traits.update",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.updated_by = self.request.user
        instance.save(update_fields=["deleted_at", "updated_by", "updated_at"])


class ReportCardListView(TenantListAPIView):
    """GET only — see the module docstring for why there's no POST here."""

    serializer_class = ReportCardSerializer

    def get_queryset(self):
        qs = ReportCard.objects.filter(deleted_at__isnull=True).prefetch_related("subjects__subject")
        student_id = self.request.query_params.get("student_id")
        term_id = self.request.query_params.get("term_id")
        class_arm_id = self.request.query_params.get("class_arm_id")
        status_filter = self.request.query_params.get("status")
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        if term_id:
            qs = qs.filter(term__public_id=term_id)
        if class_arm_id:
            qs = qs.filter(class_arm__public_id=class_arm_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.view")()]


class ReportCardDetailView(TenantRetrieveUpdateDestroyAPIView):
    """PATCH only ever touches teacher_comment/principal_comment/
    next_term_begins — every calculated field is read-only (enforced by
    the serializer's read_only_fields, not just convention)."""

    http_method_names = ["get", "patch"]
    serializer_class = ReportCardSerializer

    def get_queryset(self):
        return ReportCard.objects.filter(deleted_at__isnull=True).prefetch_related("subjects__subject")

    def get_permissions(self):
        code = "report_cards.view" if self.request.method == "GET" else "report_cards.update"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class ReportCardAuditListView(TenantListAPIView):
    """Read-only — see the module docstring on ReportCardAudit: it's
    written only by report_card_service alongside a generate/publish/
    unpublish/archive call, and the database trigger from apps.tenancy.
    db.make_append_only rejects any attempt to mutate it directly
    regardless."""

    serializer_class = ReportCardAuditSerializer

    def get_queryset(self):
        qs = ReportCardAudit.objects.select_related("changed_by")
        report_card_id = self.request.query_params.get("report_card_id")
        if report_card_id:
            qs = qs.filter(report_card__public_id=report_card_id)
        return qs

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.view")()]


class ReportCardGenerateView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.generate")()]

    def post(self, request):
        serializer = ReportCardGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            report_card = report_card_service.generate_report_card(
                student=serializer.validated_data["student"],
                term=serializer.validated_data["term"],
                actor=request.user,
            )
        except ReportCardError as exc:
            return error_envelope(str(exc), status=409)
        return envelope(ReportCardSerializer(report_card).data, message="report card generated")


class ReportCardGenerateBulkView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.generate")()]

    def post(self, request):
        serializer = ReportCardGenerateBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = report_card_service.generate_report_cards_bulk(
            term=serializer.validated_data["term"],
            students=serializer.validated_data.get("student") or None,
            actor=request.user,
        )
        return envelope(result, message="bulk generation complete")


class ReportCardBulkExportListView(TenantListAPIView):
    """Every past/in-flight bulk-export job, newest first — see
    services/report_card_bulk_export_service.py. Distinct from generate-
    bulk above: that endpoint synchronously creates/refreshes ReportCard
    rows for a class-sized batch; this tracks the async "render every
    resulting PDF into one ZIP" job for a whole term/class arm."""

    serializer_class = ReportCardBulkExportSerializer

    def get_queryset(self):
        qs = ReportCardBulkExport.objects.filter(deleted_at__isnull=True)
        term_id = self.request.query_params.get("term_id")
        if term_id:
            qs = qs.filter(term__public_id=term_id)
        return qs

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.view")()]


class ReportCardBulkExportRequestView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.generate")()]

    def post(self, request):
        serializer = ReportCardBulkExportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        export = report_card_bulk_export_service.request_bulk_export(
            term=serializer.validated_data["term"],
            class_arm=serializer.validated_data.get("class_arm"),
            actor=request.user,
        )
        return envelope(ReportCardBulkExportSerializer(export).data, message="bulk export started")


class ReportCardBulkExportDetailView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.view")()]

    def get(self, request, public_id):
        export = generics.get_object_or_404(ReportCardBulkExport.objects, public_id=public_id)
        return envelope(ReportCardBulkExportSerializer(export).data)


class ReportCardBulkExportDownloadView(APIView):
    """Same "stable link, no re-presigning" convention as ReportCardPdfView."""

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.view")()]

    def get(self, request, public_id):
        export = generics.get_object_or_404(ReportCardBulkExport.objects, public_id=public_id)
        if export.status != "ready" or not export.file_url:
            return error_envelope(f"Export not ready (status: {export.status})", status=409)
        return HttpResponseRedirect(export.file_url)


class ReportCardRegenerateView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.generate")()]

    def post(self, request, public_id):
        report_card = generics.get_object_or_404(ReportCard.objects, public_id=public_id)
        try:
            report_card = report_card_service.generate_report_card(
                student=report_card.student, term=report_card.term, actor=request.user
            )
        except ReportCardError as exc:
            return error_envelope(str(exc), status=409)
        return envelope(ReportCardSerializer(report_card).data, message="report card regenerated")


class _ReportCardTransitionView(APIView):
    transition = staticmethod(lambda *, report_card, actor: report_card)

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.publish")()]

    def post(self, request, public_id):
        report_card = generics.get_object_or_404(ReportCard.objects, public_id=public_id)
        try:
            report_card = self.transition(report_card=report_card, actor=request.user)
        except InvalidReportCardTransition as exc:
            return error_envelope(str(exc), status=409)
        return envelope(ReportCardSerializer(report_card).data)


class ReportCardPublishView(_ReportCardTransitionView):
    transition = staticmethod(report_card_service.publish_report_card)


class ReportCardUnpublishView(_ReportCardTransitionView):
    transition = staticmethod(report_card_service.unpublish_report_card)


class ReportCardPdfView(APIView):
    """A stable download link a UI can point straight at (an <a href>,
    an email link) rather than fetching JSON first to extract a field —
    redirects to the presigned URL apps.core.storage.save_file already
    produced, recomputing nothing (that URL is "generate-once-use-soon",
    per that module's docstring, not meant to be re-presigned per request).
    """

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("report_cards.view")()]

    def get(self, request, public_id):
        report_card = generics.get_object_or_404(ReportCard.objects, public_id=public_id)
        if report_card.pdf_status != "ready" or not report_card.pdf_file_url:
            return error_envelope(
                f"PDF not ready (status: {report_card.pdf_status})", status=409
            )
        return HttpResponseRedirect(report_card.pdf_file_url)


class ReportCardVerifyThrottle(AnonRateThrottle):
    scope = "report_card_verify"


class ReportCardVerifyView(APIView):
    """Public verification lookup by verification_code — no auth, no
    tenant/org scoping (see report_card_service.verify_report_card's
    docstring for why), reachable by anyone holding a printed report card
    or its QR code. Deliberately not under IsAuthenticated/require_
    permission: that's the whole point of a verification endpoint.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ReportCardVerifyThrottle]

    def get(self, request, verification_code):
        report_card = report_card_service.verify_report_card(verification_code=verification_code)
        if report_card is None:
            return error_envelope("No genuine report card found for this code", status=404)
        return envelope(ReportCardVerifySerializer(report_card).data)
