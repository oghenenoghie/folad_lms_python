"""Thin views, fat services (§11 ARCHITECTURE.md). §19's "duplicate-
allocation constraint" risk: select_for_update() on the bed row means two
racing allocate calls on the same bed can't both succeed; the partial
unique constraints in models.py back that up as real DB constraints too.
Re-allocating a student to a different bed is vacate-then-allocate, never
an in-place edit.
"""
from django.db import transaction
from django.utils import timezone

from apps.hostel.models import HostelAllocation, HostelBed
from apps.hostel.services.exceptions import BedNotAvailable
from apps.schools.models import AcademicYear
from apps.students.models import Student


def allocate_bed(
    *, student: Student, bed: HostelBed, academic_year: AcademicYear, actor, allocated_date=None
) -> HostelAllocation:
    with transaction.atomic():
        bed = HostelBed.objects.select_for_update().get(pk=bed.pk)
        if bed.status != "available":
            raise BedNotAvailable(f"bed {bed} is '{bed.status}', not available")

        HostelAllocation.objects.filter(
            student=student, academic_year=academic_year, is_active=True
        ).update(is_active=False, vacated_date=timezone.now().date(), updated_by=actor, updated_at=timezone.now())

        allocation = HostelAllocation.objects.create(
            organization=student.organization,
            student=student,
            bed=bed,
            academic_year=academic_year,
            allocated_date=allocated_date or timezone.now().date(),
            created_by=actor,
            updated_by=actor,
        )
        bed.status = "occupied"
        bed.updated_by = actor
        bed.save(update_fields=["status", "updated_by", "updated_at"])
    return allocation


def vacate_bed(*, allocation: HostelAllocation, actor) -> HostelAllocation:
    with transaction.atomic():
        allocation.is_active = False
        allocation.vacated_date = timezone.now().date()
        allocation.updated_by = actor
        allocation.save(update_fields=["is_active", "vacated_date", "updated_by", "updated_at"])

        bed = HostelBed.objects.select_for_update().get(pk=allocation.bed_id)
        bed.status = "available"
        bed.updated_by = actor
        bed.save(update_fields=["status", "updated_by", "updated_at"])
    return allocation
