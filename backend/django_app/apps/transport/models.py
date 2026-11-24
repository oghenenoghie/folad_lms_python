"""§6/§18/§19 ARCHITECTURE.md (Milestone 9). "Capacity and duplicate-
allocation constraints" is §19's named risk: TransportAssignment's partial
unique constraint below guarantees one *active* assignment per student per
academic year at the DB level (re-assigning a student is deactivate-then-
create, not an in-place edit) — vehicle seat capacity itself is a service-
layer check (services/transport_assignment_service.py), since "how many
active assignments reference this vehicle" isn't expressible as a single-
table uniqueness constraint the way one-active-assignment-per-student is.
Every model denormalizes `organization` directly, same convention as every
other app.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

VEHICLE_STATUS_CHOICES = [
    ("active", "Active"),
    ("maintenance", "Maintenance"),
    ("retired", "Retired"),
]

MAINTENANCE_STATUS_CHOICES = [
    ("scheduled", "Scheduled"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]


class Vehicle(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="vehicles")
    registration_number = models.CharField(max_length=30)
    make = models.CharField(max_length=100, blank=True, default="")
    model = models.CharField(max_length=100, blank=True, default="")
    capacity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=VEHICLE_STATUS_CHOICES, default="active")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "transport_vehicle"
        constraints = [
            models.UniqueConstraint(
                fields=["school", "registration_number"], name="uq_vehicle_school_registration"
            )
        ]
        ordering = ["registration_number"]

    def __str__(self) -> str:
        return self.registration_number


class TransportRoute(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="transport_routes")
    name = models.CharField(max_length=150)
    description = models.CharField(max_length=255, blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "transport_route"
        constraints = [
            models.UniqueConstraint(fields=["school", "name"], name="uq_transport_route_school_name")
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class RouteStop(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    route = models.ForeignKey(TransportRoute, on_delete=models.PROTECT, related_name="stops")
    name = models.CharField(max_length=150)
    sequence = models.PositiveIntegerField()
    pickup_time = models.TimeField()

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "transport_route_stop"
        constraints = [
            models.UniqueConstraint(fields=["route", "sequence"], name="uq_route_stop_route_sequence")
        ]
        ordering = ["route", "sequence"]

    def __str__(self) -> str:
        return f"{self.route}: {self.name}"


class TransportAssignment(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="transport_assignments"
    )
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="assignments")
    route = models.ForeignKey(TransportRoute, on_delete=models.PROTECT, related_name="assignments")
    stop = models.ForeignKey(RouteStop, on_delete=models.PROTECT, related_name="assignments")
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.PROTECT, related_name="transport_assignments"
    )
    assigned_date = models.DateField()
    is_active = models.BooleanField(default=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "transport_assignment"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year"],
                condition=models.Q(is_active=True),
                name="uq_transport_assignment_one_active_per_student_year",
            )
        ]
        ordering = ["-assigned_date"]

    def __str__(self) -> str:
        return f"{self.student} -> {self.route}"


class VehicleMaintenance(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    vehicle = models.ForeignKey(Vehicle, on_delete=models.PROTECT, related_name="maintenance_records")
    description = models.CharField(max_length=255)
    cost_minor = models.BigIntegerField(null=True, blank=True)
    currency_code = models.CharField(max_length=3, blank=True, default="")
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=MAINTENANCE_STATUS_CHOICES, default="scheduled")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "transport_vehicle_maintenance"
        ordering = ["-scheduled_date"]

    def __str__(self) -> str:
        return f"{self.vehicle}: {self.description}"
