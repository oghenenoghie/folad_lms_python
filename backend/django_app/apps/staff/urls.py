from django.urls import path

from .views import (
    StaffBulkImportView,
    StaffDetailView,
    StaffListCreateView,
    TeacherDetailView,
    TeacherListCreateView,
)

urlpatterns = [
    path("staff", StaffListCreateView.as_view(), name="staff-list-create"),
    path("staff/bulk-import", StaffBulkImportView.as_view(), name="staff-bulk-import"),
    path("staff/<uuid:public_id>", StaffDetailView.as_view(), name="staff-detail"),
    path("teachers", TeacherListCreateView.as_view(), name="teacher-list-create"),
    path("teachers/<uuid:public_id>", TeacherDetailView.as_view(), name="teacher-detail"),
]
