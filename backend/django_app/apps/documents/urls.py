from django.urls import path

from .views import DocumentDetailView, DocumentDownloadView, DocumentListView, DocumentUploadView

urlpatterns = [
    path("documents", DocumentListView.as_view(), name="document-list"),
    path("documents/upload", DocumentUploadView.as_view(), name="document-upload"),
    path("documents/<uuid:public_id>", DocumentDetailView.as_view(), name="document-detail"),
    path(
        "documents/<uuid:public_id>/download", DocumentDownloadView.as_view(), name="document-download"
    ),
]
