"""Thin views, fat services (§11 ARCHITECTURE.md). HostelAllocation is
create + read-only plus a dedicated vacate endpoint — reallocating a
student is vacate-then-allocate, never an in-place edit (see
allocation_service). HostelIncident gets a dedicated resolve endpoint,
mirroring apps.examinations' Result-style transition views.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import (
    TenantListCreateAPIView,
    TenantRetrieveAPIView,
    TenantRetrieveUpdateDestroyAPIView,
)
from apps.core.responses import envelope, error_envelope

from .models import Hostel, HostelAllocation, HostelBed, HostelBuilding, HostelIncident, HostelRoom
from .serializers import (
    HostelAllocationSerializer,
    HostelBedSerializer,
    HostelBuildingSerializer,
    HostelIncidentSerializer,
    HostelRoomSerializer,
    HostelSerializer,
)
from .services import allocation_service, bed_service, building_service, hostel_service, incident_service, room_service
from .services.exceptions import HostelError


class HostelListCreateView(TenantListCreateAPIView):
    serializer_class = HostelSerializer

    def get_queryset(self):
        qs = Hostel.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "hostels.create" if self.request.method == "POST" else "hostels.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = hostel_service.create_hostel(school=school, actor=self.request.user, **data)


class HostelDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = HostelSerializer

    def get_queryset(self):
        return Hostel.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "hostels.view", "PATCH": "hostels.update", "DELETE": "hostels.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        hostel_service.update_hostel(hostel=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        hostel_service.delete_hostel(hostel=instance, actor=self.request.user)


class HostelBuildingListCreateView(TenantListCreateAPIView):
    serializer_class = HostelBuildingSerializer

    def get_queryset(self):
        qs = HostelBuilding.objects.filter(deleted_at__isnull=True)
        hostel_id = self.request.query_params.get("hostel_id")
        if hostel_id:
            qs = qs.filter(hostel__public_id=hostel_id)
        return qs

    def get_permissions(self):
        code = "hostel_buildings.create" if self.request.method == "POST" else "hostel_buildings.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        hostel = data.pop("hostel")
        serializer.instance = building_service.create_building(hostel=hostel, actor=self.request.user, **data)


class HostelBuildingDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = HostelBuildingSerializer

    def get_queryset(self):
        return HostelBuilding.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "hostel_buildings.view",
            "PATCH": "hostel_buildings.update",
            "DELETE": "hostel_buildings.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("hostel", None)
        building_service.update_building(building=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        building_service.delete_building(building=instance, actor=self.request.user)


class HostelRoomListCreateView(TenantListCreateAPIView):
    serializer_class = HostelRoomSerializer

    def get_queryset(self):
        qs = HostelRoom.objects.filter(deleted_at__isnull=True)
        building_id = self.request.query_params.get("building_id")
        if building_id:
            qs = qs.filter(building__public_id=building_id)
        return qs

    def get_permissions(self):
        code = "hostel_rooms.create" if self.request.method == "POST" else "hostel_rooms.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        building = data.pop("building")
        serializer.instance = room_service.create_room(building=building, actor=self.request.user, **data)


class HostelRoomDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = HostelRoomSerializer

    def get_queryset(self):
        return HostelRoom.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "hostel_rooms.view", "PATCH": "hostel_rooms.update", "DELETE": "hostel_rooms.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("building", None)
        room_service.update_room(room=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        room_service.delete_room(room=instance, actor=self.request.user)


class HostelBedListCreateView(TenantListCreateAPIView):
    serializer_class = HostelBedSerializer

    def get_queryset(self):
        qs = HostelBed.objects.filter(deleted_at__isnull=True)
        room_id = self.request.query_params.get("room_id")
        if room_id:
            qs = qs.filter(room__public_id=room_id)
        return qs

    def get_permissions(self):
        code = "hostel_beds.create" if self.request.method == "POST" else "hostel_beds.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        room = data.pop("room")
        serializer.instance = bed_service.create_bed(room=room, actor=self.request.user, **data)


class HostelBedDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = HostelBedSerializer

    def get_queryset(self):
        return HostelBed.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "hostel_beds.view", "PATCH": "hostel_beds.update", "DELETE": "hostel_beds.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("room", None)
        bed_service.update_bed(bed=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        bed_service.delete_bed(bed=instance, actor=self.request.user)


class HostelAllocationListCreateView(TenantListCreateAPIView):
    serializer_class = HostelAllocationSerializer

    def get_queryset(self):
        qs = HostelAllocation.objects.filter(deleted_at__isnull=True)
        student_id = self.request.query_params.get("student_id")
        bed_id = self.request.query_params.get("bed_id")
        if student_id:
            qs = qs.filter(student__public_id=student_id)
        if bed_id:
            qs = qs.filter(bed__public_id=bed_id)
        return qs

    def get_permissions(self):
        code = "hostel_allocations.create" if self.request.method == "POST" else "hostel_allocations.view"
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except HostelError as exc:
            return error_envelope(str(exc), status=409)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        student = data.pop("student")
        bed = data.pop("bed")
        academic_year = data.pop("academic_year")
        serializer.instance = allocation_service.allocate_bed(
            student=student, bed=bed, academic_year=academic_year, actor=self.request.user, **data
        )


class HostelAllocationDetailView(TenantRetrieveAPIView):
    serializer_class = HostelAllocationSerializer

    def get_queryset(self):
        return HostelAllocation.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("hostel_allocations.view")()]


class HostelAllocationVacateView(APIView):
    permission_classes = [IsAuthenticated, require_permission("hostel_allocations.update")]

    def post(self, request, public_id):
        try:
            allocation = HostelAllocation.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except HostelAllocation.DoesNotExist:
            return error_envelope("allocation not found", status=404)
        allocation_service.vacate_bed(allocation=allocation, actor=request.user)
        return envelope(HostelAllocationSerializer(allocation).data, message="bed vacated")


class HostelIncidentListCreateView(TenantListCreateAPIView):
    serializer_class = HostelIncidentSerializer

    def get_queryset(self):
        qs = HostelIncident.objects.select_related("reported_by").filter(deleted_at__isnull=True)
        hostel_id = self.request.query_params.get("hostel_id")
        status_param = self.request.query_params.get("status")
        if hostel_id:
            qs = qs.filter(hostel__public_id=hostel_id)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def get_permissions(self):
        code = "hostel_incidents.create" if self.request.method == "POST" else "hostel_incidents.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        hostel = data.pop("hostel")
        serializer.instance = incident_service.report_incident(hostel=hostel, actor=self.request.user, **data)


class HostelIncidentDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = HostelIncidentSerializer

    def get_queryset(self):
        return HostelIncident.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "hostel_incidents.view",
            "PATCH": "hostel_incidents.update",
            "DELETE": "hostel_incidents.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("hostel", None)
        incident_service.update_incident(incident=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        incident_service.delete_incident(incident=instance, actor=self.request.user)


class HostelIncidentResolveView(APIView):
    permission_classes = [IsAuthenticated, require_permission("hostel_incidents.update")]

    def post(self, request, public_id):
        try:
            incident = HostelIncident.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except HostelIncident.DoesNotExist:
            return error_envelope("incident not found", status=404)
        incident_service.resolve_incident(incident=incident, actor=request.user)
        return envelope(HostelIncidentSerializer(incident).data, message="incident resolved")
