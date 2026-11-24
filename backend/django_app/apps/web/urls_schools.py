from django.urls import path

from .views.schools import (
    AcademicYearActivateView,
    AcademicYearCreateView,
    AcademicYearDeleteView,
    AcademicYearUpdateView,
    CampusCreateView,
    CampusDeleteView,
    CampusUpdateView,
    DepartmentCreateView,
    DepartmentDeleteView,
    DepartmentUpdateView,
    SchoolCreateView,
    SchoolDeleteView,
    SchoolDetailView,
    SchoolListView,
    SchoolUpdateView,
    TermActivateView,
    TermCreateView,
    TermDeleteView,
    TermUpdateView,
)

urlpatterns = [
    path("", SchoolListView.as_view(), name="school-list"),
    path("new", SchoolCreateView.as_view(), name="school-create"),
    path("<uuid:public_id>/", SchoolDetailView.as_view(), name="school-detail"),
    path("<uuid:public_id>/edit", SchoolUpdateView.as_view(), name="school-update"),
    path("<uuid:public_id>/delete", SchoolDeleteView.as_view(), name="school-delete"),
    path("<uuid:school_public_id>/campuses/new", CampusCreateView.as_view(), name="campus-create"),
    path("<uuid:school_public_id>/academic-years/new", AcademicYearCreateView.as_view(), name="academic-year-create"),
    path("<uuid:school_public_id>/departments/new", DepartmentCreateView.as_view(), name="department-create"),
]

# These act on an existing row identified by its own public_id, so they
# don't need a school in the path — kept alongside the school-nested
# create routes above rather than in a separate include for readability.
urlpatterns += [
    path("campuses/<uuid:public_id>/edit", CampusUpdateView.as_view(), name="campus-update"),
    path("campuses/<uuid:public_id>/delete", CampusDeleteView.as_view(), name="campus-delete"),
    path("academic-years/<uuid:public_id>/edit", AcademicYearUpdateView.as_view(), name="academic-year-update"),
    path("academic-years/<uuid:public_id>/delete", AcademicYearDeleteView.as_view(), name="academic-year-delete"),
    path(
        "academic-years/<uuid:public_id>/activate",
        AcademicYearActivateView.as_view(),
        name="academic-year-activate",
    ),
    path(
        "academic-years/<uuid:academic_year_public_id>/terms/new",
        TermCreateView.as_view(),
        name="term-create",
    ),
    path("terms/<uuid:public_id>/edit", TermUpdateView.as_view(), name="term-update"),
    path("terms/<uuid:public_id>/delete", TermDeleteView.as_view(), name="term-delete"),
    path("terms/<uuid:public_id>/activate", TermActivateView.as_view(), name="term-activate"),
    path("departments/<uuid:public_id>/edit", DepartmentUpdateView.as_view(), name="department-update"),
    path("departments/<uuid:public_id>/delete", DepartmentDeleteView.as_view(), name="department-delete"),
]
