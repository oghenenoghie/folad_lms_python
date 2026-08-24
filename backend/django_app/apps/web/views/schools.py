"""Thin views, fat services (§11 ARCHITECTURE.md) — every mutation here
calls the exact same apps.schools.services functions the JSON API uses,
never re-implementing school/campus/academic-year/term/department
business logic. List/detail querysets filter out soft-deleted rows
locally, matching apps.schools.views' own convention.
"""
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import TemplateView

from apps.schools.models import AcademicYear, Campus, Department, School, Term
from apps.schools.services import (
    academic_year_service,
    campus_service,
    department_service,
    school_service,
    term_service,
)

from ..forms.schools import AcademicYearForm, CampusForm, DepartmentForm, SchoolForm, TermForm
from ..permissions import can
from .base import ServiceActionView, ServiceDeleteView, ServiceFormView, WebPermissionMixin

# --- School ----------------------------------------------------------


class SchoolListView(WebPermissionMixin, TemplateView):
    permission_code = "schools.view"
    template_name = "web/schools/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumb_items"] = [("Dashboard", reverse_lazy("web:home")), ("Schools", None)]
        context["schools"] = School.objects.filter(deleted_at__isnull=True).order_by("name")
        context["can_create"] = can(self.request.user, "schools.create")
        context["can_update"] = can(self.request.user, "schools.update")
        context["can_delete"] = can(self.request.user, "schools.delete")
        context["create_form"] = SchoolForm()
        context["create_url"] = reverse("web:school-create")
        return context


class SchoolCreateView(ServiceFormView):
    permission_code = "schools.create"
    form_class = SchoolForm
    success_url = reverse_lazy("web:school-list")

    def save(self, form):
        school_service.create_school(actor=self.request.user, **form.cleaned_data)

    def get_form_context(self, form):
        return {"form": form, "post_url": reverse("web:school-create")}


class SchoolUpdateView(ServiceFormView):
    permission_code = "schools.update"
    form_class = SchoolForm

    def get_object(self):
        return get_object_or_404(School.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()
        return kwargs

    def save(self, form):
        school_service.update_school(school=self.get_object(), actor=self.request.user, **form.cleaned_data)

    def get_success_url(self):
        return reverse("web:school-detail", args=[self.kwargs["public_id"]])

    def get_form_context(self, form):
        return {"form": form, "post_url": reverse("web:school-update", args=[self.kwargs["public_id"]])}


class SchoolDeleteView(ServiceDeleteView):
    permission_code = "schools.delete"

    def delete_instance(self):
        school = get_object_or_404(School.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"])
        school_service.delete_school(school=school, actor=self.request.user)

    def get_success_url(self):
        return reverse("web:school-list")


class SchoolDetailView(WebPermissionMixin, TemplateView):
    permission_code = "schools.view"
    template_name = "web/schools/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        school = get_object_or_404(
            School.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"]
        )
        context["school"] = school
        context["breadcrumb_items"] = [
            ("Dashboard", reverse_lazy("web:home")),
            ("Schools", reverse_lazy("web:school-list")),
            (school.name, None),
        ]
        context["can_update_school"] = can(self.request.user, "schools.update")
        context["can_delete_school"] = can(self.request.user, "schools.delete")
        context["edit_form"] = SchoolForm(instance=school)
        context["school_update_url"] = reverse("web:school-update", args=[school.public_id])
        context["school_delete_url"] = reverse("web:school-delete", args=[school.public_id])

        user = self.request.user
        context["can_view_campuses"] = can(user, "campuses.view")
        context["can_create_campus"] = can(user, "campuses.create")
        can_update_campus = can(user, "campuses.update")
        can_delete_campus = can(user, "campuses.delete")
        context["can_update_campus"] = can_update_campus
        context["can_delete_campus"] = can_delete_campus
        if context["can_view_campuses"]:
            campuses = list(Campus.objects.filter(school=school, deleted_at__isnull=True).order_by("name"))
            for campus in campuses:
                campus.modal_id = f"edit-campus-{campus.public_id}"
                if can_update_campus:
                    campus.edit_form = CampusForm(instance=campus)
                    campus.update_url = reverse("web:campus-update", args=[campus.public_id])
                if can_delete_campus:
                    campus.delete_url = reverse("web:campus-delete", args=[campus.public_id])
            context["campuses"] = campuses
            context["campus_create_form"] = CampusForm()
            context["campus_create_url"] = reverse("web:campus-create", args=[school.public_id])

        context["can_view_years"] = can(user, "academic_years.view")
        context["can_create_year"] = can(user, "academic_years.create")
        can_update_year = can(user, "academic_years.update")
        can_delete_year = can(user, "academic_years.delete")
        context["can_update_year"] = can_update_year
        context["can_delete_year"] = can_delete_year
        context["can_view_terms"] = can(user, "terms.view")
        context["can_create_term"] = can(user, "terms.create")
        can_update_term = can(user, "terms.update")
        can_delete_term = can(user, "terms.delete")
        context["can_update_term"] = can_update_term
        context["can_delete_term"] = can_delete_term
        if context["can_view_years"]:
            years_qs = AcademicYear.objects.filter(school=school, deleted_at__isnull=True).order_by(
                "-start_date"
            )
            if context["can_view_terms"]:
                years_qs = years_qs.prefetch_related("terms")
            years = list(years_qs)
            for year in years:
                year.modal_id = f"edit-year-{year.public_id}"
                year.term_modal_id = f"new-term-{year.public_id}"
                if can_update_year:
                    year.edit_form = AcademicYearForm(instance=year)
                    year.update_url = reverse("web:academic-year-update", args=[year.public_id])
                if can_delete_year:
                    year.delete_url = reverse("web:academic-year-delete", args=[year.public_id])
                if can_update_year and not year.is_current:
                    year.activate_url = reverse("web:academic-year-activate", args=[year.public_id])
                if context["can_view_terms"]:
                    year.term_list = list(year.terms.filter(deleted_at__isnull=True).order_by("sequence"))
                    for term in year.term_list:
                        term.modal_id = f"edit-term-{term.public_id}"
                        if can_update_term:
                            term.edit_form = TermForm(instance=term)
                            term.update_url = reverse("web:term-update", args=[term.public_id])
                        if can_delete_term:
                            term.delete_url = reverse("web:term-delete", args=[term.public_id])
                        if can_update_term and not term.is_current:
                            term.activate_url = reverse("web:term-activate", args=[term.public_id])
                    year.term_create_url = reverse("web:term-create", args=[year.public_id])
            context["academic_years"] = years
            context["academic_year_create_form"] = AcademicYearForm()
            context["academic_year_create_url"] = reverse("web:academic-year-create", args=[school.public_id])
            context["term_create_form"] = TermForm()

        context["can_view_departments"] = can(user, "departments.view")
        context["can_create_department"] = can(user, "departments.create")
        can_update_department = can(user, "departments.update")
        can_delete_department = can(user, "departments.delete")
        context["can_update_department"] = can_update_department
        context["can_delete_department"] = can_delete_department
        if context["can_view_departments"]:
            departments = list(
                Department.objects.filter(school=school, deleted_at__isnull=True).order_by("name")
            )
            for department in departments:
                department.modal_id = f"edit-department-{department.public_id}"
                if can_update_department:
                    department.edit_form = DepartmentForm(instance=department)
                    department.update_url = reverse("web:department-update", args=[department.public_id])
                if can_delete_department:
                    department.delete_url = reverse("web:department-delete", args=[department.public_id])
            context["departments"] = departments
            context["department_create_form"] = DepartmentForm()
            context["department_create_url"] = reverse("web:department-create", args=[school.public_id])
        return context


# --- Campus ------------------------------------------------------------


class CampusCreateView(ServiceFormView):
    permission_code = "campuses.create"
    form_class = CampusForm

    def get_school(self):
        return get_object_or_404(
            School.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["school_public_id"]
        )

    def save(self, form):
        campus_service.create_campus(school=self.get_school(), actor=self.request.user, **form.cleaned_data)

    def get_success_url(self):
        return reverse("web:school-detail", args=[self.kwargs["school_public_id"]])

    def get_form_context(self, form):
        return {
            "form": form,
            "post_url": reverse("web:campus-create", args=[self.kwargs["school_public_id"]]),
        }


class CampusUpdateView(ServiceFormView):
    permission_code = "campuses.update"
    form_class = CampusForm

    def get_object(self):
        return get_object_or_404(Campus.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()
        return kwargs

    def save(self, form):
        campus_service.update_campus(campus=self.get_object(), actor=self.request.user, **form.cleaned_data)

    def get_success_url(self):
        return reverse("web:school-detail", args=[self.get_object().school.public_id])

    def get_form_context(self, form):
        return {"form": form, "post_url": reverse("web:campus-update", args=[self.kwargs["public_id"]])}


class CampusDeleteView(ServiceDeleteView):
    permission_code = "campuses.delete"

    def get_object(self):
        return get_object_or_404(Campus.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"])

    def delete_instance(self):
        campus = self.get_object()
        self._school_public_id = campus.school.public_id
        campus_service.delete_campus(campus=campus, actor=self.request.user)

    def get_success_url(self):
        return reverse("web:school-detail", args=[self._school_public_id])


# --- Academic Year -------------------------------------------------------


class AcademicYearCreateView(ServiceFormView):
    permission_code = "academic_years.create"
    form_class = AcademicYearForm

    def get_school(self):
        return get_object_or_404(
            School.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["school_public_id"]
        )

    def save(self, form):
        academic_year_service.create_academic_year(
            school=self.get_school(), actor=self.request.user, **form.cleaned_data
        )

    def get_success_url(self):
        return reverse("web:school-detail", args=[self.kwargs["school_public_id"]])

    def get_form_context(self, form):
        return {
            "form": form,
            "post_url": reverse("web:academic-year-create", args=[self.kwargs["school_public_id"]]),
        }


class AcademicYearUpdateView(ServiceFormView):
    permission_code = "academic_years.update"
    form_class = AcademicYearForm

    def get_object(self):
        return get_object_or_404(
            AcademicYear.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"]
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()
        return kwargs

    def save(self, form):
        academic_year_service.update_academic_year(
            academic_year=self.get_object(), actor=self.request.user, **form.cleaned_data
        )

    def get_success_url(self):
        return reverse("web:school-detail", args=[self.get_object().school.public_id])

    def get_form_context(self, form):
        return {
            "form": form,
            "post_url": reverse("web:academic-year-update", args=[self.kwargs["public_id"]]),
        }


class AcademicYearDeleteView(ServiceDeleteView):
    permission_code = "academic_years.delete"

    def get_object(self):
        return get_object_or_404(
            AcademicYear.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"]
        )

    def delete_instance(self):
        academic_year = self.get_object()
        self._school_public_id = academic_year.school.public_id
        academic_year_service.delete_academic_year(academic_year=academic_year, actor=self.request.user)

    def get_success_url(self):
        return reverse("web:school-detail", args=[self._school_public_id])


class AcademicYearActivateView(ServiceActionView):
    permission_code = "academic_years.update"

    def get_object(self):
        return get_object_or_404(
            AcademicYear.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"]
        )

    def perform_action(self):
        academic_year = self.get_object()
        self._school_public_id = academic_year.school.public_id
        academic_year_service.activate_academic_year(academic_year=academic_year, actor=self.request.user)

    def get_success_url(self):
        return reverse("web:school-detail", args=[self._school_public_id])


# --- Term ----------------------------------------------------------------


class TermCreateView(ServiceFormView):
    permission_code = "terms.create"
    form_class = TermForm

    def get_academic_year(self):
        return get_object_or_404(
            AcademicYear.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["academic_year_public_id"]
        )

    def save(self, form):
        term_service.create_term(academic_year=self.get_academic_year(), actor=self.request.user, **form.cleaned_data)

    def get_success_url(self):
        return reverse("web:school-detail", args=[self.get_academic_year().school.public_id])

    def get_form_context(self, form):
        return {
            "form": form,
            "post_url": reverse("web:term-create", args=[self.kwargs["academic_year_public_id"]]),
        }


class TermUpdateView(ServiceFormView):
    permission_code = "terms.update"
    form_class = TermForm

    def get_object(self):
        return get_object_or_404(Term.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()
        return kwargs

    def save(self, form):
        term_service.update_term(term=self.get_object(), actor=self.request.user, **form.cleaned_data)

    def get_success_url(self):
        return reverse("web:school-detail", args=[self.get_object().academic_year.school.public_id])

    def get_form_context(self, form):
        return {"form": form, "post_url": reverse("web:term-update", args=[self.kwargs["public_id"]])}


class TermDeleteView(ServiceDeleteView):
    permission_code = "terms.delete"

    def get_object(self):
        return get_object_or_404(Term.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"])

    def delete_instance(self):
        term = self.get_object()
        self._school_public_id = term.academic_year.school.public_id
        term_service.delete_term(term=term, actor=self.request.user)

    def get_success_url(self):
        return reverse("web:school-detail", args=[self._school_public_id])


class TermActivateView(ServiceActionView):
    permission_code = "terms.update"

    def get_object(self):
        return get_object_or_404(Term.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"])

    def perform_action(self):
        term = self.get_object()
        self._school_public_id = term.academic_year.school.public_id
        term_service.activate_term(term=term, actor=self.request.user)

    def get_success_url(self):
        return reverse("web:school-detail", args=[self._school_public_id])


# --- Department ------------------------------------------------------------


class DepartmentCreateView(ServiceFormView):
    permission_code = "departments.create"
    form_class = DepartmentForm

    def get_school(self):
        return get_object_or_404(
            School.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["school_public_id"]
        )

    def save(self, form):
        department_service.create_department(
            school=self.get_school(), actor=self.request.user, **form.cleaned_data
        )

    def get_success_url(self):
        return reverse("web:school-detail", args=[self.kwargs["school_public_id"]])

    def get_form_context(self, form):
        return {
            "form": form,
            "post_url": reverse("web:department-create", args=[self.kwargs["school_public_id"]]),
        }


class DepartmentUpdateView(ServiceFormView):
    permission_code = "departments.update"
    form_class = DepartmentForm

    def get_object(self):
        return get_object_or_404(
            Department.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"]
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.get_object()
        return kwargs

    def save(self, form):
        department_service.update_department(
            department=self.get_object(), actor=self.request.user, **form.cleaned_data
        )

    def get_success_url(self):
        return reverse("web:school-detail", args=[self.get_object().school.public_id])

    def get_form_context(self, form):
        return {
            "form": form,
            "post_url": reverse("web:department-update", args=[self.kwargs["public_id"]]),
        }


class DepartmentDeleteView(ServiceDeleteView):
    permission_code = "departments.delete"

    def get_object(self):
        return get_object_or_404(
            Department.objects.filter(deleted_at__isnull=True), public_id=self.kwargs["public_id"]
        )

    def delete_instance(self):
        department = self.get_object()
        self._school_public_id = department.school.public_id
        department_service.delete_department(department=department, actor=self.request.user)

    def get_success_url(self):
        return reverse("web:school-detail", args=[self._school_public_id])
