"""The Academic Report Card Engine: the official consolidated academic
record for one student, one academic year, one term — pulling from the
existing Result/Attendance/GradingScheme data rather than requiring a
teacher to re-enter anything (see services/report_card_service.py).

ReportCardWeighting is a per-school configuration of how much each score
category (see examinations.SCORE_CATEGORY_CHOICES) counts toward a
subject's total, e.g. CA 20% + CBT 30% + Exam 50% = 100%. ReportCard is
one student's report for one term; ReportCardSubject is one row of that
report's subject breakdown.

`status` workflow: draft -> generated (report_card_service.generate_
report_card ever only produces "generated", never "draft" — a ReportCard
row simply doesn't exist until it's generated at least once, so "draft"
is reserved for a future manual/incremental-entry workflow, not used by
the generator itself) -> published (report_card_service.publish_report_
card, admin-only) -> archived. Only "published" report cards are meant to
be visible to students/guardians; regenerating a published report reverts
it to "generated" so a human re-reviews the new numbers before
republishing, rather than silently republishing a changed document.

Every model denormalizes `organization` directly, same convention as
every other app.
"""
from django.db import models

from apps.core.models import BaseModel
from apps.tenancy.managers import TenantManager

REPORT_CARD_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("generated", "Generated"),
    ("published", "Published"),
    ("archived", "Archived"),
]


class ReportCardWeighting(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey(
        "schools.School", on_delete=models.PROTECT, related_name="report_card_weightings"
    )
    ca_weight = models.DecimalField(max_digits=5, decimal_places=2, default=30)
    cbt_weight = models.DecimalField(max_digits=5, decimal_places=2, default=30)
    exam_weight = models.DecimalField(max_digits=5, decimal_places=2, default=40)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "report_cards_weighting"
        constraints = [
            models.UniqueConstraint(fields=["school"], name="uq_report_card_weighting_school")
        ]

    def __str__(self) -> str:
        return f"{self.school}: CA {self.ca_weight} / CBT {self.cbt_weight} / Exam {self.exam_weight}"


class ReportCard(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="report_cards"
    )
    academic_year = models.ForeignKey(
        "schools.AcademicYear", on_delete=models.PROTECT, related_name="report_cards"
    )
    term = models.ForeignKey("schools.Term", on_delete=models.PROTECT, related_name="report_cards")
    # Snapshotted from the student's Enrollment at generation time — a
    # mid-term class-arm transfer shouldn't silently rewrite a report
    # that's already been generated or published.
    class_level = models.ForeignKey(
        "academics.ClassLevel", on_delete=models.PROTECT, related_name="report_cards"
    )
    class_arm = models.ForeignKey(
        "academics.ClassArm", on_delete=models.PROTECT, related_name="report_cards"
    )
    # A short, never-reused identifier for print/verification, e.g.
    # "RC-2026-000001" (see apps.core.codegen.next_sequence_code). Stable
    # across regenerations of the same student/term row.
    report_card_number = models.CharField(max_length=30, unique=True)
    # Opaque token for the public verification page (built in a later
    # phase) — generated now so it never has to be backfilled later.
    verification_code = models.CharField(max_length=64, unique=True)
    total_score = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_possible_score = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    average_percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    class_position = models.PositiveIntegerField(null=True, blank=True)
    class_size = models.PositiveIntegerField(default=0)
    attendance_present = models.PositiveIntegerField(default=0)
    attendance_absent = models.PositiveIntegerField(default=0)
    attendance_percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    teacher_comment = models.TextField(blank=True, default="")
    principal_comment = models.TextField(blank=True, default="")
    next_term_begins = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=REPORT_CARD_STATUS_CHOICES, default="draft")
    generated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "report_cards_report_card"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "academic_year", "term"], name="uq_report_card_student_year_term"
            )
        ]
        ordering = ["-academic_year", "term", "student"]

    def __str__(self) -> str:
        return f"{self.student} - {self.academic_year} {self.term} ({self.status})"


class ReportCardSubject(BaseModel):
    organization = models.ForeignKey("tenancy.Organization", on_delete=models.PROTECT, related_name="+")
    report_card = models.ForeignKey(ReportCard, on_delete=models.CASCADE, related_name="subjects")
    subject = models.ForeignKey("academics.Subject", on_delete=models.PROTECT, related_name="+")
    # Each *_score is already scaled to its category's configured weight
    # (e.g. ca_max_score = the school's ca_weight, not the raw sum of CA
    # assessment points) — see report_card_service._consolidate_subject.
    ca_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    ca_max_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    cbt_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    cbt_max_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    exam_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    exam_max_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    total_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    percentage = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    grade = models.CharField(max_length=10, blank=True, default="")
    remark = models.CharField(max_length=255, blank=True, default="")
    class_position = models.PositiveIntegerField(null=True, blank=True)
    teacher_comment = models.TextField(blank=True, default="")

    objects = TenantManager()
    all_tenants = models.Manager()

    class Meta:
        db_table = "report_cards_report_card_subject"
        constraints = [
            models.UniqueConstraint(
                fields=["report_card", "subject"], name="uq_report_card_subject_card_subject"
            )
        ]
        ordering = ["subject__name"]

    def __str__(self) -> str:
        return f"{self.report_card} - {self.subject}"
