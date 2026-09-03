"""Thin views, fat services (§11 ARCHITECTURE.md) — same convention as
apps.examinations. generate_report_card() is the Result Engine ->
Report Card Engine step from the architecture doc: it never asks a
teacher to re-enter a score, it only reads apps.examinations.Result
(published only — a result still being reviewed/verified doesn't count
yet), apps.attendance.Attendance, and apps.examinations.GradingScheme/
GradeBand, all of which already exist.

Category renormalization: a subject's total/percentage is computed only
over the score categories (CA/CBT/Exam) that actually have a published
result for it this term, rescaled to 100 — a subject with no CBT
assessment this term (e.g. an art class with only CA + a final exam)
isn't penalized for a category that was never administered. The
category-level ca_score/cbt_score/exam_score fields on ReportCardSubject
stay on their own configured-weight scale (e.g. "18/20") for a legible
printout; only the subject's total_score/percentage are renormalized.
A category with no data at all is stored as 0/0 (max 0), signalling
"not administered" to a future PDF layer rather than "scored zero".
"""
import secrets
from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from apps.academics.models import ClassArm, Enrollment
from apps.attendance.models import Attendance
from apps.core.codegen import next_sequence_code
from apps.examinations.models import Result
from apps.examinations.services.result_service import _resolve_grade
from apps.schools.models import Term
from apps.students.models import Student

from ..models import ReportCard, ReportCardSubject, ReportCardWeighting
from ..tasks.reports import generate_report_card_pdf

SCORE_CATEGORIES = ("ca", "cbt", "exam")


class ReportCardError(Exception):
    """Generation preconditions not met (e.g. no enrollment this year)."""


class InvalidReportCardTransition(Exception):
    """A publish/unpublish/archive call not valid from the current status."""


def get_or_create_weighting(*, school) -> ReportCardWeighting:
    weighting, _ = ReportCardWeighting.objects.get_or_create(
        school=school, defaults={"organization": school.organization}
    )
    return weighting


def _consolidate_subject(*, results, weighting: ReportCardWeighting) -> dict:
    by_category: dict[str, list] = {cat: [] for cat in SCORE_CATEGORIES}
    for result in results:
        by_category[result.assessment.score_category].append(result)

    row = {}
    present_weight = Decimal(0)
    weighted_sum = Decimal(0)
    for cat in SCORE_CATEGORIES:
        cat_results = by_category[cat]
        weight = getattr(weighting, f"{cat}_weight")
        if not cat_results:
            row[f"{cat}_score"] = Decimal(0)
            row[f"{cat}_max_score"] = Decimal(0)
            continue
        earned = sum((r.score for r in cat_results), Decimal(0))
        possible = sum((r.assessment.max_score for r in cat_results), Decimal(0))
        raw_pct = (earned / possible) if possible > 0 else Decimal(0)
        scaled = round(raw_pct * weight, 2)
        row[f"{cat}_score"] = scaled
        row[f"{cat}_max_score"] = weight
        present_weight += weight
        weighted_sum += scaled

    percentage = round((weighted_sum / present_weight) * 100, 2) if present_weight > 0 else Decimal(0)
    row["total_score"] = percentage
    row["percentage"] = percentage
    return row


def _recompute_positions(*, class_arm: ClassArm, term: Term) -> None:
    """Refreshes class_position/class_size on every ReportCard for this
    class_arm+term, and class_position on every ReportCardSubject of
    theirs — called after each generate_report_card so a newly generated
    or updated report always leaves the whole class's ranking consistent,
    not just the one row that changed.
    """
    cards = list(
        ReportCard.objects.filter(class_arm=class_arm, term=term).order_by(
            "-average_percentage", "student__last_name", "student__first_name"
        )
    )
    for index, card in enumerate(cards, start=1):
        if card.class_position != index or card.class_size != len(cards):
            card.class_position = index
            card.class_size = len(cards)
            card.save(update_fields=["class_position", "class_size", "updated_at"])

    subject_rows: dict[int, list] = {}
    for card in cards:
        for subject_row in card.subjects.all():
            subject_rows.setdefault(subject_row.subject_id, []).append(subject_row)
    for rows in subject_rows.values():
        rows.sort(key=lambda r: r.percentage, reverse=True)
        for index, row in enumerate(rows, start=1):
            if row.class_position != index:
                row.class_position = index
                row.save(update_fields=["class_position", "updated_at"])


def _next_report_card_number(*, organization) -> str:
    year = timezone.now().year
    prefix = f"RC-{year}-"
    return next_sequence_code(
        queryset=ReportCard.objects.filter(organization=organization),
        field_name="report_card_number",
        prefix=prefix,
        width=6,
    )


@transaction.atomic
def generate_report_card(*, student: Student, term: Term, actor) -> ReportCard:
    academic_year = term.academic_year
    enrollment = (
        Enrollment.objects.filter(student=student, academic_year=academic_year)
        .select_related("class_arm__class_level")
        .first()
    )
    if enrollment is None:
        raise ReportCardError(f"{student} has no enrollment for {academic_year}")

    weighting = get_or_create_weighting(school=student.school)

    results = (
        Result.objects.filter(
            student=student,
            assessment__term=term,
            status="published",
            deleted_at__isnull=True,
        )
        .select_related("assessment__class_subject__subject")
    )
    by_subject: dict[int, list] = {}
    for result in results:
        subject = result.assessment.class_subject.subject
        by_subject.setdefault(subject.id, []).append(result)

    report_card, _ = ReportCard.objects.get_or_create(
        student=student,
        academic_year=academic_year,
        term=term,
        defaults={
            "organization": student.organization,
            "class_level": enrollment.class_arm.class_level,
            "class_arm": enrollment.class_arm,
            "report_card_number": _next_report_card_number(organization=student.organization),
            "verification_code": secrets.token_urlsafe(24),
            "created_by": actor,
            "updated_by": actor,
        },
    )

    total_score = Decimal(0)
    for subject_id, subject_results in by_subject.items():
        row = _consolidate_subject(results=subject_results, weighting=weighting)
        grade, remark = _resolve_grade(school=student.school, score=row["percentage"])
        ReportCardSubject.objects.update_or_create(
            report_card=report_card,
            subject_id=subject_id,
            defaults={
                "organization": student.organization,
                "grade": grade,
                "remark": remark,
                **row,
            },
        )
        total_score += row["total_score"]

    # Drop any subject row from a previous generation that no longer has a
    # published result this term (e.g. a result was un-published/deleted).
    ReportCardSubject.objects.filter(report_card=report_card).exclude(
        subject_id__in=by_subject.keys()
    ).delete()

    subject_count = len(by_subject)
    average_percentage = round(total_score / subject_count, 2) if subject_count else Decimal(0)

    attendance_qs = Attendance.objects.filter(
        enrollment=enrollment, date__gte=term.start_date, date__lte=term.end_date
    )
    present = attendance_qs.filter(status="present").count()
    absent = attendance_qs.filter(status="absent").count()
    attendance_percentage = round((present / (present + absent)) * 100, 2) if (present + absent) else Decimal(0)

    report_card.class_level = enrollment.class_arm.class_level
    report_card.class_arm = enrollment.class_arm
    report_card.total_score = total_score
    report_card.total_possible_score = subject_count * 100
    report_card.average_percentage = average_percentage
    report_card.attendance_present = present
    report_card.attendance_absent = absent
    report_card.attendance_percentage = attendance_percentage
    # A regenerate always drops back to "generated" even if it was
    # published — the numbers just changed, so a human re-reviews before
    # republishing rather than silently republishing a changed document.
    report_card.status = "generated"
    report_card.published_at = None
    report_card.generated_at = timezone.now()
    report_card.updated_by = actor
    report_card.save(
        update_fields=[
            "class_level", "class_arm", "total_score", "total_possible_score", "average_percentage",
            "attendance_present", "attendance_absent", "attendance_percentage",
            "status", "published_at", "generated_at", "updated_by", "updated_at",
        ]
    )

    _recompute_positions(class_arm=enrollment.class_arm, term=term)
    report_card.refresh_from_db()

    # Deferred to on_commit: the whole function above is one atomic block,
    # so a worker picking this up before it commits would find no row yet.
    report_card_id, organization_id = report_card.id, report_card.organization_id
    transaction.on_commit(lambda: generate_report_card_pdf.delay(report_card_id, organization_id))

    return report_card


def generate_report_cards_bulk(*, term: Term, students=None, actor) -> dict:
    """Synchronous bulk generation — fine for a class-sized batch. A real
    "generate for the whole school" run belongs on a Celery queue (see
    apps.examinations' old generate_report_card_pdf for the established
    pattern in this codebase); that's a later phase, not implemented here.
    `students=None` means "every student enrolled this academic year".
    """
    if students is None:
        students = Student.objects.filter(enrollments__academic_year=term.academic_year).distinct()

    generated = []
    failed = []
    for student in students:
        try:
            report_card = generate_report_card(student=student, term=term, actor=actor)
        except ReportCardError as exc:
            failed.append({"student": str(student.public_id), "error": str(exc)})
        else:
            generated.append(str(report_card.public_id))
    return {"generated": generated, "failed": failed}


def publish_report_card(*, report_card: ReportCard, actor) -> ReportCard:
    if report_card.status != "generated":
        raise InvalidReportCardTransition(
            f"cannot publish a report card in status '{report_card.status}' (must be 'generated')"
        )
    report_card.status = "published"
    report_card.published_at = timezone.now()
    report_card.updated_by = actor
    report_card.save(update_fields=["status", "published_at", "updated_by", "updated_at"])
    return report_card


def unpublish_report_card(*, report_card: ReportCard, actor) -> ReportCard:
    if report_card.status != "published":
        raise InvalidReportCardTransition(
            f"cannot unpublish a report card in status '{report_card.status}' (must be 'published')"
        )
    report_card.status = "generated"
    report_card.published_at = None
    report_card.updated_by = actor
    report_card.save(update_fields=["status", "published_at", "updated_by", "updated_at"])
    return report_card


def verify_report_card(*, verification_code: str) -> ReportCard | None:
    """Public lookup for the verification page/QR code — no authenticated
    org context exists at this point (same reason apps.accounts.auth_
    service queries User.all_tenants rather than the tenant-scoped
    manager), so this bypasses TenantManager/RLS entirely and relies on
    verification_code's own uniqueness + unguessability instead. Only a
    report card that was actually issued (published, or later archived)
    verifies — "generated" (not yet reviewed/published) and "draft" never
    do, so a not-yet-released report card can't be confirmed early.
    """
    return (
        ReportCard.all_tenants.filter(
            verification_code=verification_code,
            status__in=("published", "archived"),
            deleted_at__isnull=True,
        )
        .select_related("student__school", "academic_year", "term", "class_level", "class_arm")
        # Prefetch.queryset must also use all_tenants: the plain "subjects"
        # relation goes through ReportCardSubject's default TenantManager,
        # which would filter to an active org context that doesn't exist
        # on this unauthenticated request and silently come back empty.
        .prefetch_related(
            Prefetch(
                "subjects",
                queryset=ReportCardSubject.all_tenants.select_related("subject").order_by(
                    "subject__name"
                ),
            )
        )
        .first()
    )


def archive_report_card(*, report_card: ReportCard, actor) -> ReportCard:
    if report_card.status not in ("generated", "published"):
        raise InvalidReportCardTransition(
            f"cannot archive a report card in status '{report_card.status}'"
        )
    report_card.status = "archived"
    report_card.updated_by = actor
    report_card.save(update_fields=["status", "updated_by", "updated_at"])
    return report_card
