"""§4/§6/§18 ARCHITECTURE.md (Milestone 6: attendance audit trail).
Attendance hangs off `academics.Enrollment` (§5 ERD: ENROLLMENT ||--o{
ATTENDANCE : records) — one row per enrollment per day. AttendanceAudit
records every status change and is genuinely append-only: its migration
attaches a Postgres trigger (apps.tenancy.db.make_append_only) that
rejects UPDATE and DELETE at the database level, not just by convention —
§15 ARCHITECTURE.md: "Immutable audit ... by DB trigger." Both models
denormalize `organization` directly, same convention as every other app.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

ATTENDANCE_STATUS_CHOICES = [
    ("present", "Present"),
    ("absent", "Absent"),
    ("late", "Late"),
    ("excused", "Excused"),
    ("leave", "Leave"),
    ("half_day", "Half day"),
]


class Attendance(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    enrollment = models.ForeignKey(
        "academics.Enrollment", on_delete=models.PROTECT, related_name="attendance_records"
    )
    date = models.DateField()
    status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES, default="present")
    remarks = models.CharField(max_length=255, blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "attendance_attendance"
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "date"], name="uq_attendance_enrollment_date")
        ]
        # RLS (see apps.tenancy.db.enable_rls) injects an organization_id =
        # ... predicate into every query on this table; the dashboard's
        # date-range widgets (attendance_today_pct, weekly_attendance_series,
        # attendance_heatmap) then filter by date on top of that — this is
        # the single fastest-growing table in the schema (one row per
        # enrollment per school day), so that combination is worth its own
        # index rather than relying on the enrollment+date unique constraint
        # above, which doesn't help a date-only/date-range filter.
        indexes = [models.Index(fields=["organization", "date"], name="idx_attendance_org_date")]
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.enrollment} - {self.date} ({self.status})"


class AttendanceAudit(BaseModel):
    """Append-only: see the module docstring. Only ever inserted, never
    updated or soft-deleted — `updated_by`/`deleted_at` (inherited from
    BaseModel for the same public_id/timestamp shape every other model
    uses) are consequently always unset, and the DB trigger rejects any
    attempt to change that.
    """

    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    attendance = models.ForeignKey(
        Attendance, on_delete=models.PROTECT, related_name="audit_entries"
    )
    previous_status = models.CharField(
        max_length=20, choices=ATTENDANCE_STATUS_CHOICES, blank=True, default=""
    )
    new_status = models.CharField(max_length=20, choices=ATTENDANCE_STATUS_CHOICES)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "attendance_attendance_audit"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.attendance} : {self.previous_status or '(new)'} -> {self.new_status}"
