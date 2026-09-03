"""Thin views, fat services (§11 ARCHITECTURE.md) — same convention as
apps.examinations. ReportCard has no client-facing create/update/delete
via the generic CRUD verbs: it's only ever produced by generate/
generate-bulk and transitioned by publish/unpublish, mirroring how
apps.examinations.Result's workflow transitions are dedicated APIView
endpoints rather than a generic PATCH.
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

from .models import ReportCard, ReportCardWeighting
from .serializers import (
    ReportCardGenerateBulkSerializer,
    ReportCardGenerateSerializer,
    ReportCardSerializer,
    ReportCardWeightingSerializer,
)
from .services import report_card_service
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


class ReportCardListView(TenantListAPIView):
    """GET only — see the module docstring for why there's no POST here."""

    serializer_class = ReportCardSerializer

    def get_queryset(self):
        qs = ReportCard.objects.filter(deleted_at__isnull=True).prefetch_related("subjects")
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
        return ReportCard.objects.filter(deleted_at__isnull=True).prefetch_related("subjects")

    def get_permissions(self):
        code = "report_cards.view" if self.request.method == "GET" else "report_cards.update"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


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
