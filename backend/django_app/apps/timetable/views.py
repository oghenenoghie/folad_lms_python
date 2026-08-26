"""Thin views, fat services (§11 ARCHITECTURE.md). Parent-FK fields are
write-required on create but stripped before update — re-parenting a
resource to a different parent would leave its denormalized
`organization` (and, for TimetableSlot, `class_arm`/`teacher`) stale (see
models.py), so re-assigning a slot to a different class_subject is a
deliberate delete-and-recreate rather than an in-place update, same
convention as every other app.
"""
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView

from .models import Period, Room, TimetableSlot
from .serializers import PeriodSerializer, RoomSerializer, TimetableSlotSerializer
from .services import period_service, room_service, timetable_slot_service


class RoomListCreateView(TenantListCreateAPIView):
    serializer_class = RoomSerializer

    def get_queryset(self):
        qs = Room.objects.filter(deleted_at__isnull=True)
        campus_id = self.request.query_params.get("campus_id")
        if campus_id:
            qs = qs.filter(campus__public_id=campus_id)
        return qs

    def get_permissions(self):
        code = "rooms.create" if self.request.method == "POST" else "rooms.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        campus = data.pop("campus")
        serializer.instance = room_service.create_room(campus=campus, actor=self.request.user, **data)


class RoomDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = RoomSerializer

    def get_queryset(self):
        return Room.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "rooms.view", "PATCH": "rooms.update", "DELETE": "rooms.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("campus", None)
        room_service.update_room(room=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        room_service.delete_room(room=instance, actor=self.request.user)


class PeriodListCreateView(TenantListCreateAPIView):
    serializer_class = PeriodSerializer

    def get_queryset(self):
        qs = Period.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "periods.create" if self.request.method == "POST" else "periods.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = period_service.create_period(school=school, actor=self.request.user, **data)


class PeriodDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = PeriodSerializer

    def get_queryset(self):
        return Period.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "periods.view", "PATCH": "periods.update", "DELETE": "periods.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        period_service.update_period(period=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        period_service.delete_period(period=instance, actor=self.request.user)


class TimetableSlotListCreateView(TenantListCreateAPIView):
    serializer_class = TimetableSlotSerializer

    def get_queryset(self):
        qs = TimetableSlot.objects.filter(deleted_at__isnull=True)
        class_arm_id = self.request.query_params.get("class_arm_id")
        teacher_id = self.request.query_params.get("teacher_id")
        room_id = self.request.query_params.get("room_id")
        if class_arm_id:
            qs = qs.filter(class_arm__public_id=class_arm_id)
        if teacher_id:
            qs = qs.filter(teacher__public_id=teacher_id)
        if room_id:
            qs = qs.filter(room__public_id=room_id)
        return qs

    def get_permissions(self):
        code = "timetable_slots.create" if self.request.method == "POST" else "timetable_slots.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        class_subject = data.pop("class_subject")
        serializer.instance = timetable_slot_service.create_timetable_slot(
            class_subject=class_subject, actor=self.request.user, **data
        )


class TimetableSlotDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = TimetableSlotSerializer

    def get_queryset(self):
        return TimetableSlot.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "timetable_slots.view",
            "PATCH": "timetable_slots.update",
            "DELETE": "timetable_slots.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("class_subject", None)
        timetable_slot_service.update_timetable_slot(
            timetable_slot=serializer.instance, actor=self.request.user, **data
        )

    def perform_destroy(self, instance):
        timetable_slot_service.delete_timetable_slot(timetable_slot=instance, actor=self.request.user)
