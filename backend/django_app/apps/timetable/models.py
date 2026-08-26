"""§4/§6/§18/§19 ARCHITECTURE.md (Milestone 6: timetable, conflict
detection — the module's named risk is "teacher/room/class double-
booking"). TimetableSlot denormalizes `class_arm` and `teacher` from its
`class_subject` (derived server-side, never accepted from client input,
same convention `organization` already uses everywhere) specifically so
every kind of double-booking is a real database UniqueConstraint on
(x, day_of_week, period) rather than an application-layer check with a
race-condition window — a slot is a genuine conflict the moment two rows
would share a teacher, class arm, or room at the same day+period, and
Postgres enforces that atomically. `room` is nullable (some lessons don't
need a fixed room), so its constraint is conditional on `room` being set.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

DAY_OF_WEEK_CHOICES = [
    ("monday", "Monday"),
    ("tuesday", "Tuesday"),
    ("wednesday", "Wednesday"),
    ("thursday", "Thursday"),
    ("friday", "Friday"),
    ("saturday", "Saturday"),
    ("sunday", "Sunday"),
]


class Room(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    campus = models.ForeignKey("schools.Campus", on_delete=models.PROTECT, related_name="rooms")
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "timetable_room"
        constraints = [models.UniqueConstraint(fields=["campus", "name"], name="uq_room_campus_name")]
        ordering = ["campus", "name"]

    def __str__(self) -> str:
        return self.name


class Period(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="periods")
    name = models.CharField(max_length=100)
    sequence = models.PositiveSmallIntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "timetable_period"
        constraints = [
            models.UniqueConstraint(fields=["school", "sequence"], name="uq_period_school_sequence"),
            models.UniqueConstraint(fields=["school", "name"], name="uq_period_school_name"),
        ]
        ordering = ["school", "sequence"]

    def __str__(self) -> str:
        return self.name


class TimetableSlot(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    class_subject = models.ForeignKey(
        "academics.ClassSubject", on_delete=models.PROTECT, related_name="timetable_slots"
    )
    class_arm = models.ForeignKey(
        "academics.ClassArm", on_delete=models.PROTECT, related_name="timetable_slots"
    )
    teacher = models.ForeignKey(
        "staff.Teacher", on_delete=models.PROTECT, related_name="timetable_slots"
    )
    room = models.ForeignKey(
        Room, null=True, blank=True, on_delete=models.PROTECT, related_name="timetable_slots"
    )
    day_of_week = models.CharField(max_length=10, choices=DAY_OF_WEEK_CHOICES)
    period = models.ForeignKey(Period, on_delete=models.PROTECT, related_name="timetable_slots")
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "timetable_slot"
        constraints = [
            models.UniqueConstraint(
                fields=["teacher", "day_of_week", "period"], name="uq_timetable_teacher_slot"
            ),
            models.UniqueConstraint(
                fields=["class_arm", "day_of_week", "period"], name="uq_timetable_class_slot"
            ),
            models.UniqueConstraint(
                fields=["room", "day_of_week", "period"],
                name="uq_timetable_room_slot",
                condition=models.Q(room__isnull=False),
            ),
        ]
        ordering = ["day_of_week", "period"]

    def __str__(self) -> str:
        return f"{self.class_arm} - {self.class_subject.subject} ({self.day_of_week}, {self.period})"
