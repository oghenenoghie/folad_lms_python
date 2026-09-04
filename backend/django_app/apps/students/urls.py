from django.urls import path

from .views import StudentBulkImportView, StudentDetailView, StudentListCreateView

urlpatterns = [
    path("students", StudentListCreateView.as_view(), name="student-list-create"),
    path("students/bulk-import", StudentBulkImportView.as_view(), name="student-bulk-import"),
    path("students/<uuid:public_id>", StudentDetailView.as_view(), name="student-detail"),
]
