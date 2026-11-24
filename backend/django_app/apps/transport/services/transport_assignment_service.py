"""Thin views, fat services (§11 ARCHITECTURE.md). §19's "capacity ...
constraint" risk: select_for_update() on the vehicle row serializes
concurrent assign calls so two racing requests can't together exceed
vehicle.capacity — a count-then-compare check DB uniqueness alone can't
express. Re-assigning a student is deactivate-then-create, never an
in-place edit, so uq_transport_assignment_one_active_per_student_year
(models.py) never sees two active rows to conflict on.
"""
from django.db import transaction
from django.utils import timezone

from apps.schools.models import AcademicYear
from apps.students.models import Student
from apps.transport.models import RouteStop, TransportAssignment, TransportRoute, Vehicle
from apps.transport.services.exceptions import VehicleAtCapacity


def assign_transport(
    *, student: Student, vehicle: Vehicle, route: TransportRoute, stop: RouteStop,
    academic_year: AcademicYear, actor, assigned_date=None,
) -> TransportAssignment:
    with transaction.atomic():
        vehicle = Vehicle.objects.select_for_update().get(pk=vehicle.pk)
        active_count = TransportAssignment.objects.filter(vehicle=vehicle, is_active=True).count()
        if active_count >= vehicle.capacity:
            raise VehicleAtCapacity(f"vehicle {vehicle} is at capacity ({vehicle.capacity})")

        TransportAssignment.objects.filter(
            student=student, academic_year=academic_year, is_active=True
        ).update(is_active=False, updated_by=actor, updated_at=timezone.now())

        return TransportAssignment.objects.create(
            organization=student.organization,
            student=student,
            vehicle=vehicle,
            route=route,
            stop=stop,
            academic_year=academic_year,
            assigned_date=assigned_date or timezone.now().date(),
            created_by=actor,
            updated_by=actor,
        )


def unassign_transport(*, assignment: TransportAssignment, actor) -> TransportAssignment:
    assignment.is_active = False
    assignment.updated_by = actor
    assignment.save(update_fields=["is_active", "updated_by", "updated_at"])
    return assignment
