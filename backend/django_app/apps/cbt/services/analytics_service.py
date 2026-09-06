"""Post-hoc exam analytics: exam-level summary stats and per-question item
analysis (facility index, discrimination index). Read-only reporting over
ExamAttempt/StudentAnswer — never writes anything, and never a competing
source of truth for a score (that's attempt_service.finalize_attempt).

Every figure here is computed only over attempts whose score is final —
`submitted`/`expired` with nothing left ungraded — so an exam that still
has pending subjective grading never reports skewed, half-finished
numbers.
"""
from decimal import Decimal

from apps.cbt.models import ExamAttempt, StudentAnswer

# The standard "upper-lower 27%" method for a discrimination index
# (Kelley, 1939): split finalized attempts into the top and bottom 27% by
# total score, then for each item, discrimination = (top group's correct
# rate) - (bottom group's correct rate). A well-discriminating item is one
# strong candidates get right far more often than weak ones; a value near
# zero or negative flags a miskeyed, ambiguous, or trivial item.
_UPPER_LOWER_FRACTION = Decimal("0.27")

# Ten fixed percentage buckets: [0, 10), [10, 20), ..., [90, 100].
_DISTRIBUTION_BUCKETS = 10


def _finalized_attempts(exam):
    """Attempts whose score is settled: submitted/expired, with no answer
    still awaiting a human grade. Excludes not_started/in_progress/
    abandoned attempts entirely."""
    return (
        ExamAttempt.objects.filter(exam=exam, status__in=["submitted", "expired"])
        .exclude(answers__graded_at__isnull=True)
        .distinct()
    )


def _score_distribution(percentages: list[Decimal]) -> list[dict]:
    buckets = [0] * _DISTRIBUTION_BUCKETS
    for pct in percentages:
        index = min(int(pct) // 10, _DISTRIBUTION_BUCKETS - 1)
        buckets[index] += 1
    return [
        {"range": f"{i * 10}-{i * 10 + 9 if i < _DISTRIBUTION_BUCKETS - 1 else 100}", "count": count}
        for i, count in enumerate(buckets)
    ]


def exam_summary(*, exam) -> dict:
    """Exam-wide figures: how many candidates were assigned, how many
    attempts exist in each stage, and — over finalized attempts only —
    the average score/percentage, pass rate, and a percentage-score
    histogram.
    """
    attempts_started = exam.attempts.exclude(status="not_started").count()
    finalized = list(_finalized_attempts(exam))
    total = len(finalized)
    if total == 0:
        return {
            "total_candidates": exam.candidates.count(),
            "attempts_started": attempts_started,
            "finalized_attempts": 0,
            "average_score": None,
            "average_percentage": None,
            "pass_rate": None,
            "score_distribution": _score_distribution([]),
        }

    scores = [a.score for a in finalized]
    percentages = [a.percentage for a in finalized]
    passed = sum(1 for a in finalized if a.passed)
    return {
        "total_candidates": exam.candidates.count(),
        "attempts_started": attempts_started,
        "finalized_attempts": total,
        "average_score": str(round(sum(scores) / total, 2)),
        "average_percentage": str(round(sum(percentages) / total, 2)),
        "pass_rate": str(round(Decimal(passed) / total * 100, 2)),
        "score_distribution": _score_distribution(percentages),
    }


def item_analysis(*, exam) -> list[dict]:
    """Per-question stats over the same finalized-attempts population as
    exam_summary. "Correct" for this purpose is full marks awarded
    (marks_awarded >= the question's effective marks) — not
    StudentAnswer.is_correct, which is always null for a manually-graded
    subjective answer and would otherwise silently exclude those
    questions from the analysis.
    """
    exam_questions = list(exam.exam_questions.select_related("question").order_by("order"))
    finalized = list(_finalized_attempts(exam))
    if not finalized:
        return [
            {
                "exam_question": str(eq.public_id),
                "question_code": eq.question.code,
                "answered_count": 0,
                "correct_count": 0,
                "facility_index": None,
                "discrimination_index": None,
            }
            for eq in exam_questions
        ]

    ranked = sorted(finalized, key=lambda a: a.score, reverse=True)
    group_size = max(1, round(len(ranked) * _UPPER_LOWER_FRACTION))
    upper_ids = {a.id for a in ranked[:group_size]}
    lower_ids = {a.id for a in ranked[-group_size:]}
    attempt_ids = [a.id for a in finalized]

    rows = []
    for eq in exam_questions:
        answers = list(StudentAnswer.objects.filter(exam_question=eq, attempt_id__in=attempt_ids))
        answered_count = len(answers)
        full_marks = eq.marks
        correct_count = sum(1 for ans in answers if ans.marks_awarded >= full_marks)
        facility_index = round(Decimal(correct_count) / answered_count, 2) if answered_count else None

        upper_correct = sum(1 for ans in answers if ans.attempt_id in upper_ids and ans.marks_awarded >= full_marks)
        lower_correct = sum(1 for ans in answers if ans.attempt_id in lower_ids and ans.marks_awarded >= full_marks)
        discrimination_index = round(Decimal(upper_correct - lower_correct) / group_size, 2)

        rows.append(
            {
                "exam_question": str(eq.public_id),
                "question_code": eq.question.code,
                "answered_count": answered_count,
                "correct_count": correct_count,
                "facility_index": str(facility_index) if facility_index is not None else None,
                "discrimination_index": str(discrimination_index),
            }
        )
    return rows
