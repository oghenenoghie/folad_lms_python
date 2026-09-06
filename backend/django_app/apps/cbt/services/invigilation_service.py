"""Live invigilation: a staff-facing, poll-based snapshot of every
candidate's current status during an exam window. Not a websocket feed —
nothing in this stack pushes server events to a browser — so the client
is expected to re-poll; a GET here is read-only and cheap enough to call
every few seconds for a class-sized exam. Read-only, like
analytics_service: never writes anything, and never a competing view of
an attempt's actual state (that stays attempt_service).
"""
from django.db.models import Count, Max
from django.utils import timezone


def live_status(*, exam) -> list[dict]:
    """One row per candidate, in candidate_number order: their attempt's
    current status, time remaining (server-computed, never trusting a
    client clock), progress, whether they're flagged, and their most
    recent activity (started_at/an answer/a proctoring event, whichever
    is latest) — a stalled "last activity" during an in-progress attempt
    is itself a useful invigilation signal.
    """
    now = timezone.now()
    total_questions = exam.exam_questions.count()

    attempts = {
        attempt.candidate_id: attempt
        for attempt in exam.attempts.annotate(
            answered_count=Count("answers", distinct=True),
            last_answer_at=Max("answers__answered_at"),
            last_event_at=Max("events__created_at"),
        )
    }

    rows = []
    for candidate in exam.candidates.select_related("student").order_by("candidate_number"):
        attempt = attempts.get(candidate.id)
        row = {
            "candidate": str(candidate.public_id),
            "candidate_number": candidate.candidate_number,
            "student_name": f"{candidate.student.first_name} {candidate.student.last_name}",
            "is_eligible": candidate.is_eligible,
            "status": "not_started",
            "answered_count": 0,
            "total_questions": total_questions,
            "seconds_remaining": None,
            "flagged_for_review": False,
            "last_activity_at": None,
        }
        if attempt is not None:
            seconds_remaining = None
            if attempt.status == "in_progress" and attempt.expires_at:
                seconds_remaining = max(0, int((attempt.expires_at - now).total_seconds()))
            last_activity_at = max(
                (t for t in (attempt.started_at, attempt.last_answer_at, attempt.last_event_at) if t is not None),
                default=None,
            )
            row.update(
                {
                    "status": attempt.status,
                    "answered_count": attempt.answered_count,
                    "seconds_remaining": seconds_remaining,
                    "flagged_for_review": attempt.flagged_for_review,
                    "last_activity_at": last_activity_at,
                }
            )
        rows.append(row)
    return rows
