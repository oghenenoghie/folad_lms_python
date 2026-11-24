"""Thin views, fat services (§11 ARCHITECTURE.md). Upload is multipart, not
plain JSON create — DocumentUploadSerializer validates only the non-file
fields; the file itself comes from request.FILES and is validated by
apps.core.storage.validate_upload (MIME + magic bytes + size) inside
document_service.upload_document. Download never returns a stored URL —
it computes a fresh presigned one at request time, after the same
IsAuthenticated + RBAC + tenant-scoped get_queryset() check every other
detail view already goes through (§14: "generated only after an
authorization + tenant-ownership check").
"""
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListAPIView, TenantRetrieveUpdateDestroyAPIView
from apps.core.responses import envelope, error_envelope
from apps.core.storage import InvalidUpload
from apps.schools.models import School

from .models import Document
from .serializers import DocumentSerializer, DocumentUploadSerializer
from .services import document_service
from .services.exceptions import DocumentError


class DocumentListView(TenantListAPIView):
    serializer_class = DocumentSerializer

    def get_queryset(self):
        qs = Document.objects.filter(deleted_at__isnull=True)
        student_id = self.request.query_params.get("student_id")
        staff_id = self.request.query_params.get("staff_id")
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        if staff_id:
            qs = qs.filter(staff__public_id=staff_id)
        return qs

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("documents.view")()]


class DocumentDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return Document.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "documents.view", "PATCH": "documents.update", "DELETE": "documents.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        document_service.update_document(
            document=serializer.instance, actor=self.request.user, **serializer.validated_data
        )

    def perform_destroy(self, instance):
        document_service.delete_document(document=instance, actor=self.request.user)


class DocumentUploadView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated, require_permission("documents.create")]

    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        school_public_id = request.data.get("school")
        try:
            school = School.objects.get(public_id=school_public_id)
        except (School.DoesNotExist, ValueError, TypeError):
            return error_envelope("school not found", status=404)

        file_obj = request.FILES.get("file")
        if file_obj is None:
            return error_envelope("a file is required", status=400)

        try:
            document = document_service.upload_document(
                school=school,
                actor=request.user,
                document_type=data["document_type"],
                title=data["title"],
                file_name=file_obj.name,
                content=file_obj.read(),
                content_type=file_obj.content_type,
                student=data.get("student"),
                staff=data.get("staff"),
            )
        except (DocumentError, InvalidUpload) as exc:
            return error_envelope(str(exc), status=400)
        return envelope(DocumentSerializer(document).data, message="document uploaded", status=201)


class DocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated, require_permission("documents.view")]

    def get(self, request, public_id):
        try:
            document = Document.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except Document.DoesNotExist:
            return error_envelope("document not found", status=404)
        url = document_service.get_download_url(document)
        return envelope({"url": url})
