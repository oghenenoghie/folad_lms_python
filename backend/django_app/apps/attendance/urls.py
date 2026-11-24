from django.urls import path

from .views import AttendanceAuditListView, AttendanceDetailView, AttendanceListCreateView

urlpatterns = [
    path("attendance", AttendanceListCreateView.as_view(), name="attendance-list-create"),
    path("attendance/<uuid:public_id>", AttendanceDetailView.as_view(), name="attendance-detail"),
    path("attendance-audit", AttendanceAuditListView.as_view(), name="attendance-audit-list"),
]
