"""Thin views, fat services (§11 ARCHITECTURE.md). Every status change —
on create and on update — writes an AttendanceAudit row first, inside the
same transaction, so the append-only trail always reflects reality even
if the Attendance row itself is later corrected again.
"""
from django.db import transaction
from django.utils import timezone

from apps.academics.models import Enrollment
from apps.attendance.models import Attendance, AttendanceAudit


def mark_attendance(*, enrollment: Enrollment, actor, status: str, **fields) -> Attendance:
    with transaction.atomic():
        attendance = Attendance.objects.create(
            organization=enrollment.organization,
            enrollment=enrollment,
            status=status,
            created_by=actor,
            updated_by=actor,
            **fields,
        )
        AttendanceAudit.objects.create(
            organization=enrollment.organization,
            attendance=attendance,
            previous_status="",
            new_status=status,
            changed_by=actor,
            created_by=actor,
            updated_by=actor,
        )
    return attendance


def update_attendance(*, attendance: Attendance, actor, **fields) -> Attendance:
    with transaction.atomic():
        new_status = fields.get("status")
        if new_status and new_status != attendance.status:
            AttendanceAudit.objects.create(
                organization=attendance.organization,
                attendance=attendance,
                previous_status=attendance.status,
                new_status=new_status,
                changed_by=actor,
                created_by=actor,
                updated_by=actor,
            )
        for field, value in fields.items():
            setattr(attendance, field, value)
        attendance.updated_by = actor
        attendance.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return attendance


def delete_attendance(*, attendance: Attendance, actor) -> None:
    attendance.deleted_at = timezone.now()
    attendance.updated_by = actor
    attendance.save(update_fields=["deleted_at", "updated_by", "updated_at"])
