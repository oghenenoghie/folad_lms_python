from django.urls import path

from .views import StaffDetailView, StaffListCreateView, TeacherDetailView, TeacherListCreateView

urlpatterns = [
    path("staff", StaffListCreateView.as_view(), name="staff-list-create"),
    path("staff/<uuid:public_id>", StaffDetailView.as_view(), name="staff-detail"),
    path("teachers", TeacherListCreateView.as_view(), name="teacher-list-create"),
    path("teachers/<uuid:public_id>", TeacherDetailView.as_view(), name="teacher-detail"),
]
