from django.urls import path

from .views import (
    ClassArmDetailView,
    ClassArmListCreateView,
    ClassLevelDetailView,
    ClassLevelListCreateView,
    ClassSubjectDetailView,
    ClassSubjectListCreateView,
    EnrollmentDetailView,
    EnrollmentListCreateView,
    SubjectDetailView,
    SubjectListCreateView,
)

urlpatterns = [
    path("class-levels", ClassLevelListCreateView.as_view(), name="class-level-list-create"),
    path("class-levels/<uuid:public_id>", ClassLevelDetailView.as_view(), name="class-level-detail"),
    path("class-arms", ClassArmListCreateView.as_view(), name="class-arm-list-create"),
    path("class-arms/<uuid:public_id>", ClassArmDetailView.as_view(), name="class-arm-detail"),
    path("subjects", SubjectListCreateView.as_view(), name="subject-list-create"),
    path("subjects/<uuid:public_id>", SubjectDetailView.as_view(), name="subject-detail"),
    path("class-subjects", ClassSubjectListCreateView.as_view(), name="class-subject-list-create"),
    path("class-subjects/<uuid:public_id>", ClassSubjectDetailView.as_view(), name="class-subject-detail"),
    path("enrollments", EnrollmentListCreateView.as_view(), name="enrollment-list-create"),
    path("enrollments/<uuid:public_id>", EnrollmentDetailView.as_view(), name="enrollment-detail"),
]
