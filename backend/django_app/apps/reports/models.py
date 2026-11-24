"""§4/§18 ARCHITECTURE.md (Milestone 11, the REP box in §4's "Insight"
subgraph). ReportRequest tracks one async export job — same pending ->
generating -> ready/failed lifecycle and storage_key/get_presigned_download_url
shape as apps.examinations.ReportCard and apps.finance.Receipt, generalized
across report types instead of being specific to one document. `parameters`
is a JSON bag (e.g. {"term_id": "...", "class_arm_id": "..."}) since each
report_type takes a different shape of filter — see
services/generators.py for what each one actually reads out of it.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

REPORT_TYPE_CHOICES = [
    ("student_list", "Student list"),
    ("attendance_summary", "Attendance summary"),
    ("fee_collection", "Fee collection"),
    ("results_summary", "Results summary"),
]

REPORT_FORMAT_CHOICES = [
    ("csv", "CSV"),
    ("xlsx", "Excel"),
    ("pdf", "PDF"),
]

REPORT_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("generating", "Generating"),
    ("ready", "Ready"),
    ("failed", "Failed"),
]


class ReportRequest(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey("schools.School", on_delete=models.PROTECT, related_name="report_requests")
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    format = models.CharField(max_length=10, choices=REPORT_FORMAT_CHOICES)
    parameters = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=REPORT_STATUS_CHOICES, default="pending")
    storage_key = models.CharField(max_length=500, blank=True, default="")
    file_name = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=100, blank=True, default="")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=255, blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "reports_report_request"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.report_type} ({self.format}) - {self.status}"
