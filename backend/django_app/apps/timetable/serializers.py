from rest_framework import serializers

from apps.academics.models import ClassSubject
from apps.core.serializers import PublicIdRelatedField
from apps.schools.models import Campus, School

from .models import Period, Room, TimetableSlot


class RoomSerializer(serializers.ModelSerializer):
    # `Campus.objects` (the manager), not `.all()` — see academics'
    # serializers for why: a pre-built queryset would freeze TenantManager's
    # org-scoping at import time (no request context yet).
    campus = PublicIdRelatedField(queryset=Campus.objects)

    class Meta:
        model = Room
        fields = ["public_id", "campus", "name", "capacity", "is_active"]
        validators = []


class PeriodSerializer(serializers.ModelSerializer):
    school = PublicIdRelatedField(queryset=School.objects)

    class Meta:
        model = Period
        fields = ["public_id", "school", "name", "sequence", "start_time", "end_time", "is_active"]
        validators = []


class TimetableSlotSerializer(serializers.ModelSerializer):
    class_subject = PublicIdRelatedField(queryset=ClassSubject.objects)
    class_arm = PublicIdRelatedField(read_only=True)
    teacher = PublicIdRelatedField(read_only=True)
    room = PublicIdRelatedField(queryset=Room.objects, required=False, allow_null=True)
    period = PublicIdRelatedField(queryset=Period.objects)

    class Meta:
        model = TimetableSlot
        fields = [
            "public_id",
            "class_subject",
            "class_arm",
            "teacher",
            "room",
            "day_of_week",
            "period",
            "is_active",
        ]
        # class_arm/teacher/room/day_of_week/period participate in this
        # model's UniqueConstraints and are all serializer-visible, so DRF
        # would otherwise auto-add UniqueTogetherValidators — bypassing the
        # envelope with a raw 400 instead of the clean 409
        # EnvelopeCreateMixin's IntegrityError handler produces (see
        # core/generics.py).
        validators = []
