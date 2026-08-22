"""Thin views, fat services (§11 ARCHITECTURE.md). Every list/detail view
here filters out soft-deleted rows locally (`deleted_at__isnull=True`) —
see the soft-delete note in models.py; this isn't (yet) pushed into
TenantManager since no other app needs it.

Parent-FK fields (`school`, `academic_year`) are write-required on create
but stripped before update: re-parenting a row would leave its
denormalized `organization` stale (see models.py's module docstring), so
plain PATCH silently ignores attempts to change the parent — moving a
resource to a different parent is a deliberate operation out of M3 scope.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView
from apps.core.responses import envelope, error_envelope

from .models import AcademicYear, Campus, Department, School, Term
from .serializers import (
    AcademicYearSerializer,
    CampusSerializer,
    DepartmentSerializer,
    SchoolSerializer,
    TermSerializer,
)
from .services import (
    academic_year_service,
    campus_service,
    department_service,
    school_service,
    term_service,
)


class SchoolListCreateView(TenantListCreateAPIView):
    serializer_class = SchoolSerializer

    def get_queryset(self):
        return School.objects.filter(deleted_at__isnull=True).order_by("name")

    def get_permissions(self):
        code = "schools.create" if self.request.method == "POST" else "schools.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        serializer.instance = school_service.create_school(
            actor=self.request.user, **serializer.validated_data
        )


class SchoolDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = SchoolSerializer

    def get_queryset(self):
        return School.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "schools.view", "PATCH": "schools.update", "DELETE": "schools.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        school_service.update_school(
            school=serializer.instance, actor=self.request.user, **serializer.validated_data
        )

    def perform_destroy(self, instance):
        school_service.delete_school(school=instance, actor=self.request.user)


class CampusListCreateView(TenantListCreateAPIView):
    serializer_class = CampusSerializer

    def get_queryset(self):
        qs = Campus.objects.filter(deleted_at__isnull=True).order_by("name")
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "campuses.create" if self.request.method == "POST" else "campuses.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = campus_service.create_campus(school=school, actor=self.request.user, **data)


class CampusDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = CampusSerializer

    def get_queryset(self):
        return Campus.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "campuses.view", "PATCH": "campuses.update", "DELETE": "campuses.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        campus_service.update_campus(campus=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        campus_service.delete_campus(campus=instance, actor=self.request.user)


class AcademicYearListCreateView(TenantListCreateAPIView):
    serializer_class = AcademicYearSerializer

    def get_queryset(self):
        qs = AcademicYear.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "academic_years.create" if self.request.method == "POST" else "academic_years.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = academic_year_service.create_academic_year(
            school=school, actor=self.request.user, **data
        )


class AcademicYearDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = AcademicYearSerializer

    def get_queryset(self):
        return AcademicYear.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "academic_years.view",
            "PATCH": "academic_years.update",
            "DELETE": "academic_years.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        academic_year_service.update_academic_year(
            academic_year=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        academic_year_service.delete_academic_year(academic_year=instance, actor=self.request.user)


class AcademicYearActivateView(APIView):
    permission_classes = [IsAuthenticated, require_permission("academic_years.update")]

    def post(self, request, public_id):
        try:
            academic_year = AcademicYear.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except AcademicYear.DoesNotExist:
            return error_envelope("academic year not found", status=404)
        academic_year_service.activate_academic_year(academic_year=academic_year, actor=request.user)
        return envelope(AcademicYearSerializer(academic_year).data, message="academic year activated")


class TermListCreateView(TenantListCreateAPIView):
    serializer_class = TermSerializer

    def get_queryset(self):
        qs = Term.objects.filter(deleted_at__isnull=True)
        academic_year_id = self.request.query_params.get("academic_year_id")
        if academic_year_id:
            qs = qs.filter(academic_year__public_id=academic_year_id)
        return qs

    def get_permissions(self):
        code = "terms.create" if self.request.method == "POST" else "terms.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        academic_year = data.pop("academic_year")
        serializer.instance = term_service.create_term(
            academic_year=academic_year, actor=self.request.user, **data
        )


class TermDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = TermSerializer

    def get_queryset(self):
        return Term.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "terms.view", "PATCH": "terms.update", "DELETE": "terms.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("academic_year", None)
        term_service.update_term(term=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        term_service.delete_term(term=instance, actor=self.request.user)


class TermActivateView(APIView):
    permission_classes = [IsAuthenticated, require_permission("terms.update")]

    def post(self, request, public_id):
        try:
            term = Term.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except Term.DoesNotExist:
            return error_envelope("term not found", status=404)
        term_service.activate_term(term=term, actor=request.user)
        return envelope(TermSerializer(term).data, message="term activated")


class DepartmentListCreateView(TenantListCreateAPIView):
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        qs = Department.objects.filter(deleted_at__isnull=True).order_by("name")
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "departments.create" if self.request.method == "POST" else "departments.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = department_service.create_department(
            school=school, actor=self.request.user, **data
        )


class DepartmentDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        return Department.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "departments.view", "PATCH": "departments.update", "DELETE": "departments.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        department_service.update_department(department=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        department_service.delete_department(department=instance, actor=self.request.user)
