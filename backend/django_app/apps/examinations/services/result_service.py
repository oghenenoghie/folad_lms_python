"""Thin views, fat services (§11 ARCHITECTURE.md). Result carries the M7
exit criterion's enter->submit->review->verify->publish workflow: each
transition function below validates the current status is exactly the
expected predecessor, then writes a ResultWorkflowState audit row and
updates Result.status in the same transaction — same pattern
apps.attendance.services.attendance_service already established for
Attendance/AttendanceAudit. `score`/`grade`/`remark` are only editable
while a Result is still "entered"; once submitted, correcting a mistake
means walking it back through the workflow, not editing in place.
"""
from django.db import transaction
from django.utils import timezone

from apps.examinations.models import Assessment, GradeBand, Result, ResultWorkflowState
from apps.students.models import Student

_WORKFLOW_ORDER = ["entered", "submitted", "reviewed", "verified", "published"]


class InvalidResultTransition(Exception):
    pass


def _resolve_grade(*, school, score) -> tuple[str, str]:
    """Best-effort: returns ("", "") rather than raising when no grading
    scheme is configured yet, or no band covers this score — grading
    configuration is optional, not a precondition for entering a result.
    """
    band = (
        GradeBand.objects.filter(
            grading_scheme__school=school,
            grading_scheme__is_default=True,
            min_score__lte=score,
            max_score__gte=score,
        )
        .order_by("-min_score")
        .first()
    )
    return (band.grade, band.remark) if band else ("", "")


def enter_result(*, assessment: Assessment, student: Student, actor, score, **fields) -> Result:
    grade, remark = _resolve_grade(school=assessment.class_subject.subject.school, score=score)
    return Result.objects.create(
        organization=assessment.organization,
        assessment=assessment,
        student=student,
        score=score,
        grade=fields.pop("grade", grade),
        remark=fields.pop("remark", remark),
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_result(*, result: Result, actor, **fields) -> Result:
    if result.status != "entered":
        raise InvalidResultTransition(
            f"cannot edit a result once it has moved past 'entered' (current status: {result.status})"
        )
    if "score" in fields and "grade" not in fields and "remark" not in fields:
        grade, remark = _resolve_grade(
            school=result.assessment.class_subject.subject.school, score=fields["score"]
        )
        fields["grade"], fields["remark"] = grade, remark
    for field, value in fields.items():
        setattr(result, field, value)
    result.updated_by = actor
    result.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return result


def delete_result(*, result: Result, actor) -> None:
    result.deleted_at = timezone.now()
    result.updated_by = actor
    result.save(update_fields=["deleted_at", "updated_by", "updated_at"])


def _transition(*, result: Result, actor, new_status: str) -> Result:
    expected_index = _WORKFLOW_ORDER.index(new_status) - 1
    if expected_index < 0 or result.status != _WORKFLOW_ORDER[expected_index]:
        raise InvalidResultTransition(
            f"cannot move a result from '{result.status}' to '{new_status}'"
        )
    with transaction.atomic():
        ResultWorkflowState.objects.create(
            organization=result.organization,
            result=result,
            previous_status=result.status,
            new_status=new_status,
            changed_by=actor,
            created_by=actor,
            updated_by=actor,
        )
        result.status = new_status
        result.updated_by = actor
        result.save(update_fields=["status", "updated_by", "updated_at"])
    return result


def submit_result(*, result: Result, actor) -> Result:
    return _transition(result=result, actor=actor, new_status="submitted")


def review_result(*, result: Result, actor) -> Result:
    return _transition(result=result, actor=actor, new_status="reviewed")


def verify_result(*, result: Result, actor) -> Result:
    return _transition(result=result, actor=actor, new_status="verified")


def publish_result(*, result: Result, actor) -> Result:
    return _transition(result=result, actor=actor, new_status="published")
