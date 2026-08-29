"""Thin views, fat services (§11 ARCHITECTURE.md). TransportAssignment has
no update — reassigning a student is unassign-then-assign (see
transport_assignment_service), same pattern as apps.examinations.Invigilator.
"""
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import require_permission
from apps.core.generics import (
    EnvelopeDestroyMixin,
    EnvelopeRetrieveMixin,
    TenantListCreateAPIView,
    TenantRetrieveUpdateDestroyAPIView,
)
from apps.core.responses import error_envelope

from .models import RouteStop, TransportAssignment, TransportRoute, Vehicle, VehicleMaintenance
from .serializers import (
    RouteStopSerializer,
    TransportAssignmentSerializer,
    TransportRouteSerializer,
    VehicleMaintenanceSerializer,
    VehicleSerializer,
)
from .services import (
    route_service,
    route_stop_service,
    transport_assignment_service,
    vehicle_maintenance_service,
    vehicle_service,
)
from .services.exceptions import TransportError


class VehicleListCreateView(TenantListCreateAPIView):
    serializer_class = VehicleSerializer

    def get_queryset(self):
        qs = Vehicle.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "vehicles.create" if self.request.method == "POST" else "vehicles.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = vehicle_service.create_vehicle(school=school, actor=self.request.user, **data)


class VehicleDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = VehicleSerializer

    def get_queryset(self):
        return Vehicle.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "vehicles.view", "PATCH": "vehicles.update", "DELETE": "vehicles.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        vehicle_service.update_vehicle(vehicle=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        vehicle_service.delete_vehicle(vehicle=instance, actor=self.request.user)


class TransportRouteListCreateView(TenantListCreateAPIView):
    serializer_class = TransportRouteSerializer

    def get_queryset(self):
        qs = TransportRoute.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "transport_routes.create" if self.request.method == "POST" else "transport_routes.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = route_service.create_route(school=school, actor=self.request.user, **data)


class TransportRouteDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = TransportRouteSerializer

    def get_queryset(self):
        return TransportRoute.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "transport_routes.view",
            "PATCH": "transport_routes.update",
            "DELETE": "transport_routes.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        route_service.update_route(route=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        route_service.delete_route(route=instance, actor=self.request.user)


class RouteStopListCreateView(TenantListCreateAPIView):
    serializer_class = RouteStopSerializer

    def get_queryset(self):
        qs = RouteStop.objects.filter(deleted_at__isnull=True)
        route_id = self.request.query_params.get("route_id")
        if route_id:
            qs = qs.filter(route__public_id=route_id)
        return qs

    def get_permissions(self):
        code = "route_stops.create" if self.request.method == "POST" else "route_stops.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        route = data.pop("route")
        serializer.instance = route_stop_service.create_route_stop(
            route=route, actor=self.request.user, **data
        )


class RouteStopDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = RouteStopSerializer

    def get_queryset(self):
        return RouteStop.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "route_stops.view", "PATCH": "route_stops.update", "DELETE": "route_stops.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("route", None)
        route_stop_service.update_route_stop(route_stop=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        route_stop_service.delete_route_stop(route_stop=instance, actor=self.request.user)


class TransportAssignmentListCreateView(TenantListCreateAPIView):
    serializer_class = TransportAssignmentSerializer

    def get_queryset(self):
        qs = TransportAssignment.objects.filter(deleted_at__isnull=True)
        student_id = self.request.query_params.get("student_id")
        vehicle_id = self.request.query_params.get("vehicle_id")
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        if vehicle_id:
            qs = qs.filter(vehicle__public_id=vehicle_id)
        return qs

    def get_permissions(self):
        code = (
            "transport_assignments.create" if self.request.method == "POST" else "transport_assignments.view"
        )
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except TransportError as exc:
            return error_envelope(str(exc), status=409)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        student = data.pop("student")
        vehicle = data.pop("vehicle")
        route = data.pop("route")
        stop = data.pop("stop")
        academic_year = data.pop("academic_year")
        serializer.instance = transport_assignment_service.assign_transport(
            student=student, vehicle=vehicle, route=route, stop=stop,
            academic_year=academic_year, actor=self.request.user, **data,
        )


class TransportAssignmentDetailView(EnvelopeRetrieveMixin, EnvelopeDestroyMixin, generics.GenericAPIView):
    """GET + DELETE only — no update. DELETE calls unassign_transport
    (is_active=False), not a hard delete or soft-delete via deleted_at;
    reassigning a student is unassign-then-assign (see the module
    docstring)."""

    serializer_class = TransportAssignmentSerializer
    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    def get_queryset(self):
        return TransportAssignment.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = "transport_assignments.view" if self.request.method == "GET" else "transport_assignments.delete"
        return [IsAuthenticated(), require_permission(code)()]

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        transport_assignment_service.unassign_transport(assignment=instance, actor=self.request.user)


class VehicleMaintenanceListCreateView(TenantListCreateAPIView):
    serializer_class = VehicleMaintenanceSerializer

    def get_queryset(self):
        qs = VehicleMaintenance.objects.filter(deleted_at__isnull=True)
        vehicle_id = self.request.query_params.get("vehicle_id")
        if vehicle_id:
            qs = qs.filter(vehicle__public_id=vehicle_id)
        return qs

    def get_permissions(self):
        code = (
            "vehicle_maintenance.create" if self.request.method == "POST" else "vehicle_maintenance.view"
        )
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        vehicle = data.pop("vehicle")
        serializer.instance = vehicle_maintenance_service.schedule_maintenance(
            vehicle=vehicle, actor=self.request.user, **data
        )


class VehicleMaintenanceDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = VehicleMaintenanceSerializer

    def get_queryset(self):
        return VehicleMaintenance.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "vehicle_maintenance.view",
            "PATCH": "vehicle_maintenance.update",
            "DELETE": "vehicle_maintenance.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("vehicle", None)
        vehicle_maintenance_service.update_maintenance(
            maintenance=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        vehicle_maintenance_service.delete_maintenance(maintenance=instance, actor=self.request.user)
