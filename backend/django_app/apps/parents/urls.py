from django.urls import path

from .views import (
    GuardianDetailView,
    GuardianListCreateView,
    GuardianStudentDetailView,
    GuardianStudentListCreateView,
)

urlpatterns = [
    path("guardians", GuardianListCreateView.as_view(), name="guardian-list-create"),
    path("guardians/<uuid:public_id>", GuardianDetailView.as_view(), name="guardian-detail"),
    path("guardian-students", GuardianStudentListCreateView.as_view(), name="guardian-student-list-create"),
    path(
        "guardian-students/<uuid:public_id>",
        GuardianStudentDetailView.as_view(),
        name="guardian-student-detail",
    ),
]
