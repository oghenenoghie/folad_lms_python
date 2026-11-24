"""Thin views, fat services (§11 ARCHITECTURE.md). A submission is text or a
file, never both — the two entry points below are the only way to create
one, so that invariant never depends on the caller remembering to clear the
other field. Grading is a separate, explicit action (grade_submission), not
a plain field update — a submission is never silently re-opened for editing
once graded (see views.py, which only exposes create + this one transition).
"""
from django.db import transaction
from django.utils import timezone

from apps.assignments.models import Assignment, AssignmentSubmission
from apps.assignments.services.exceptions import InvalidSubmission
from apps.core.storage import get_presigned_download_url, save_document, validate_upload
from apps.students.models import Student


def _status_for(assignment: Assignment, submitted_at) -> str:
    due = assignment.due_date
    submitted_date = submitted_at.date() if hasattr(submitted_at, "date") else submitted_at
    return "late" if submitted_date > due else "submitted"


def submit_text(*, assignment: Assignment, student: Student, actor, text_content: str) -> AssignmentSubmission:
    if not text_content.strip():
        raise InvalidSubmission("text_content must not be empty")
    submitted_at = timezone.now()
    return AssignmentSubmission.objects.create(
        organization=assignment.organization,
        assignment=assignment,
        student=student,
        text_content=text_content,
        submitted_at=submitted_at,
        status=_status_for(assignment, submitted_at),
        created_by=actor,
        updated_by=actor,
    )


def submit_file(
    *, assignment: Assignment, student: Student, actor, file_name: str, content: bytes, content_type: str
) -> AssignmentSubmission:
    validate_upload(content=content, content_type=content_type)
    storage_key = save_document(
        key_prefix=f"assignment-submissions/{assignment.organization_id}",
        filename=file_name,
        content=content,
        content_type=content_type,
    )
    submitted_at = timezone.now()
    return AssignmentSubmission.objects.create(
        organization=assignment.organization,
        assignment=assignment,
        student=student,
        storage_key=storage_key,
        file_name=file_name,
        content_type=content_type,
        size_bytes=len(content),
        submitted_at=submitted_at,
        status=_status_for(assignment, submitted_at),
        created_by=actor,
        updated_by=actor,
    )


def grade_submission(*, submission: AssignmentSubmission, actor, score, feedback: str = "") -> AssignmentSubmission:
    with transaction.atomic():
        submission.score = score
        submission.feedback = feedback
        submission.status = "graded"
        submission.graded_at = timezone.now()
        submission.updated_by = actor
        submission.save(
            update_fields=["score", "feedback", "status", "graded_at", "updated_by", "updated_at"]
        )
    return submission


def get_download_url(submission: AssignmentSubmission) -> str | None:
    if not submission.storage_key:
        return None
    return get_presigned_download_url(submission.storage_key)
