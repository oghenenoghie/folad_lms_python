from django.urls import path

from .views import (
    AcademicYearActivateView,
    AcademicYearDetailView,
    AcademicYearListCreateView,
    CampusDetailView,
    CampusListCreateView,
    DepartmentDetailView,
    DepartmentListCreateView,
    SchoolDetailView,
    SchoolListCreateView,
    TermActivateView,
    TermDetailView,
    TermListCreateView,
)

urlpatterns = [
    path("schools", SchoolListCreateView.as_view(), name="school-list-create"),
    path("schools/<uuid:public_id>", SchoolDetailView.as_view(), name="school-detail"),
    path("campuses", CampusListCreateView.as_view(), name="campus-list-create"),
    path("campuses/<uuid:public_id>", CampusDetailView.as_view(), name="campus-detail"),
    path("academic-years", AcademicYearListCreateView.as_view(), name="academic-year-list-create"),
    path("academic-years/<uuid:public_id>", AcademicYearDetailView.as_view(), name="academic-year-detail"),
    path(
        "academic-years/<uuid:public_id>/activate",
        AcademicYearActivateView.as_view(),
        name="academic-year-activate",
    ),
    path("terms", TermListCreateView.as_view(), name="term-list-create"),
    path("terms/<uuid:public_id>", TermDetailView.as_view(), name="term-detail"),
    path("terms/<uuid:public_id>/activate", TermActivateView.as_view(), name="term-activate"),
    path("departments", DepartmentListCreateView.as_view(), name="department-list-create"),
    path("departments/<uuid:public_id>", DepartmentDetailView.as_view(), name="department-detail"),
]
