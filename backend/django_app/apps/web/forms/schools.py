"""ModelForms mirroring apps.schools.serializers' field lists, minus the
parent FK (school / academic_year) — that's supplied by the view from
the URL it's nested under, not picked from a dropdown, since every one
of these pages already lives on its parent's detail page. `is_current`
is excluded from AcademicYearForm/TermForm for the same reason the API
serializer marks it read-only: it's a specialized "Activate" action
(apps.schools.services activate_academic_year/activate_term), not a
plain field edit — see views/schools.py's Activate views.
"""
from django import forms

from apps.schools.models import AcademicYear, Campus, Department, School, Term

from .base import StyledModelForm

_DATE_WIDGETS = {
    "start_date": forms.DateInput(attrs={"type": "date"}),
    "end_date": forms.DateInput(attrs={"type": "date"}),
}


class SchoolForm(StyledModelForm):
    class Meta:
        model = School
        fields = ["name", "code", "address", "phone", "email", "default_grading_scheme", "is_active"]


class CampusForm(StyledModelForm):
    class Meta:
        model = Campus
        fields = ["name", "code", "address", "is_main", "is_active"]


class AcademicYearForm(StyledModelForm):
    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "end_date", "is_active"]
        widgets = _DATE_WIDGETS


class TermForm(StyledModelForm):
    class Meta:
        model = Term
        fields = ["name", "sequence", "start_date", "end_date", "is_active"]
        widgets = _DATE_WIDGETS


class DepartmentForm(StyledModelForm):
    class Meta:
        model = Department
        fields = ["name", "code", "description", "is_active"]
