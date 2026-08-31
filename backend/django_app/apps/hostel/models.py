"""§6/§18/§19 ARCHITECTURE.md (Milestone 9). "Capacity and duplicate-
allocation constraints" is §19's named risk, same as apps.transport:
HostelAllocation carries two partial unique constraints — one bed can have
only one active occupant, and one student can hold only one active
allocation per academic year — both real DB constraints, not just
application-layer checks. Every model denormalizes `organization` directly,
same convention as every other app.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

HOSTEL_TYPE_CHOICES = [
    ("boys", "Boys"),
    ("girls", "Girls"),
    ("mixed", "Mixed"),
]

BED_STATUS_CHOICES = [
    ("available", "Available"),
    ("occupied", "Occupied"),
    ("maintenance", "Maintenance"),
]

INCIDENT_SEVERITY_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]

INCIDENT_STATUS_CHOICES = [
    ("open", "Open"),
    ("resolved", "Resolved"),
]


class Hostel(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="hostels")
    name = models.CharField(max_length=150)
    hostel_type = models.CharField(max_length=10, choices=HOSTEL_TYPE_CHOICES)
    warden = models.ForeignKey(
        "staff.Staff", null=True, blank=True, on_delete=models.SET_NULL, related_name="wardened_hostels"
    )

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "hostel_hostel"
        constraints = [models.UniqueConstraint(fields=["school", "name"], name="uq_hostel_school_name")]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class HostelBuilding(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    hostel = models.ForeignKey(Hostel, on_delete=models.PROTECT, related_name="buildings")
    name = models.CharField(max_length=150)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "hostel_building"
        constraints = [
            models.UniqueConstraint(fields=["hostel", "name"], name="uq_hostel_building_hostel_name")
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.hostel}: {self.name}"


class HostelRoom(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    building = models.ForeignKey(HostelBuilding, on_delete=models.PROTECT, related_name="rooms")
    # Optional: left blank, save() assigns the next sequential number for
    # this building (e.g. "1", "2") — see apps.core.codegen. Type the real
    # room number instead when it needs to match the building's own signage.
    room_number = models.CharField(max_length=30, blank=True)
    capacity = models.PositiveIntegerField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "hostel_room"
        constraints = [
            models.UniqueConstraint(fields=["building", "room_number"], name="uq_hostel_room_building_number")
        ]
        ordering = ["room_number"]

    def __str__(self) -> str:
        return f"{self.building}: {self.room_number}"

    def save(self, *args, **kwargs):
        if not self.room_number:
            from apps.core.codegen import next_sequence_code

            self.room_number = next_sequence_code(
                queryset=HostelRoom.all_tenants.filter(building_id=self.building_id),
                field_name="room_number",
                width=1,
            )
        super().save(*args, **kwargs)


class HostelBed(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    room = models.ForeignKey(HostelRoom, on_delete=models.PROTECT, related_name="beds")
    # Optional: left blank, save() assigns the next sequential number for
    # this room (e.g. "1", "2") — see apps.core.codegen. Type the real bed
    # number instead when it needs to match the room's own labeling.
    bed_number = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=20, choices=BED_STATUS_CHOICES, default="available")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "hostel_bed"
        constraints = [
            models.UniqueConstraint(fields=["room", "bed_number"], name="uq_hostel_bed_room_number")
        ]
        ordering = ["bed_number"]

    def __str__(self) -> str:
        return f"{self.room}: {self.bed_number}"

    def save(self, *args, **kwargs):
        if not self.bed_number:
            from apps.core.codegen import next_sequence_code

            self.bed_number = next_sequence_code(
                queryset=HostelBed.all_tenants.filter(room_id=self.room_id),
                field_name="bed_number",
                width=1,
            )
        super().save(*args, **kwargs)


class HostelAllocation(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="hostel_allocations"
    )
    bed = models.ForeignKey(HostelBed, on_delete=models.PROTECT, related_name="allocations")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.PROTECT, related_name="hostel_allocations"
    )
    allocated_date = models.DateField()
    vacated_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "hostel_allocation"
        constraints = [
            models.UniqueConstraint(
                fields=["bed"], condition=models.Q(is_active=True), name="uq_hostel_allocation_one_active_per_bed"
            ),
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                condition=models.Q(is_active=True),
                name="uq_hostel_allocation_one_active_per_student_year",
            ),
        ]
        ordering = ["-allocated_date"]

    def __str__(self) -> str:
        return f"{self.student} -> {self.bed}"


class HostelIncident(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    hostel = models.ForeignKey(Hostel, on_delete=models.PROTECT, related_name="incidents")
    room = models.ForeignKey(
        HostelRoom, null=True, blank=True, on_delete=models.PROTECT, related_name="incidents"
    )
    student = models.ForeignKey(
        "students.Student", null=True, blank=True, on_delete=models.PROTECT, related_name="hostel_incidents"
    )
    reported_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    description = models.CharField(max_length=500)
    severity = models.CharField(max_length=10, choices=INCIDENT_SEVERITY_CHOICES, default="low")
    status = models.CharField(max_length=20, choices=INCIDENT_STATUS_CHOICES, default="open")
    occurred_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "hostel_incident"
        ordering = ["-occurred_at"]

    def __str__(self) -> str:
        return f"{self.hostel}: {self.description[:40]}"
