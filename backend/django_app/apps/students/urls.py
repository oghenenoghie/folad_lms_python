from django.urls import path

from .views import (
    GuardianStudentDetailView,
    GuardianStudentListCreateView,
    StudentDetailView,
    StudentListCreateView,
)

urlpatterns = [
    path("students", StudentListCreateView.as_view(), name="student-list-create"),
    path("students/<uuid:public_id>", StudentDetailView.as_view(), name="student-detail"),
    path("student-guardians", GuardianStudentListCreateView.as_view(), name="student-guardian-list-create"),
    path(
        "student-guardians/<uuid:public_id>",
        GuardianStudentDetailView.as_view(),
        name="student-guardian-detail",
    ),
]
