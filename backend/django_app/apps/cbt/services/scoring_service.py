"""Scores one StudentAnswer's `response` against its ExamQuestion's frozen
`snapshot` (never the live Question — see ExamQuestion.marks' docstring on
why: the attempt is scored against exactly what the candidate was shown,
not whatever the bank question has become since). Covers every
AUTO_GRADABLE_QUESTION_TYPES entry; a subjective type is never graded
here — see apps.cbt.services.attempt_service.grade_subjective_answer.
"""
from decimal import Decimal

from apps.cbt.models import AUTO_GRADABLE_QUESTION_TYPES


class ScoringError(ValueError):
    pass


def _correct_option_labels(snapshot: dict) -> set[str]:
    return {o["label"] for o in snapshot["options"] if o["is_correct"]}


def _grade_single_choice(*, snapshot: dict, response: dict) -> bool:
    return response.get("selected_option_label") in _correct_option_labels(snapshot)


def _grade_multiple_choice(*, snapshot: dict, response: dict) -> bool:
    selected = set(response.get("selected_option_labels", []))
    return selected == _correct_option_labels(snapshot)


def _grade_true_false(*, snapshot: dict, response: dict) -> bool:
    return response.get("selected_option_label") in _correct_option_labels(snapshot)


def _grade_numeric(*, snapshot: dict, response: dict) -> bool:
    """The correct value and an optional tolerance live in the first
    option's `content` (e.g. `{"value": 42, "tolerance": 0.5}`) — numeric
    questions have no is_correct-flagged options, just one answer key.
    """
    if not snapshot["options"]:
        raise ScoringError("numeric question has no configured answer key")
    key = snapshot["options"][0]["content"]
    try:
        expected = Decimal(str(key["value"]))
        given = Decimal(str(response.get("value")))
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        raise ScoringError(f"invalid numeric response or answer key: {exc}") from exc
    tolerance = Decimal(str(key.get("tolerance", 0)))
    return abs(given - expected) <= tolerance


def _grade_matching(*, snapshot: dict, response: dict) -> bool:
    """The correct mapping lives in the first option's `content` (e.g.
    `{"matches": {"A": "3", "B": "1"}}`)."""
    if not snapshot["options"]:
        raise ScoringError("matching question has no configured answer key")
    expected = snapshot["options"][0]["content"].get("matches", {})
    return response.get("matches", {}) == expected


def _grade_ordering(*, snapshot: dict, response: dict) -> bool:
    """The correct sequence lives in the first option's `content` (e.g.
    `{"sequence": ["3", "1", "2"]}`)."""
    if not snapshot["options"]:
        raise ScoringError("ordering question has no configured answer key")
    expected = snapshot["options"][0]["content"].get("sequence", [])
    return response.get("sequence", []) == expected


def _grade_hotspot(*, snapshot: dict, response: dict) -> bool:
    """The target region lives in the first option's `content` (e.g.
    `{"x": 432, "y": 271, "tolerance": 20}`) — a click within `tolerance`
    pixels of the target counts."""
    if not snapshot["options"]:
        raise ScoringError("hotspot question has no configured answer key")
    target = snapshot["options"][0]["content"]
    try:
        dx = float(response.get("x", 0)) - float(target["x"])
        dy = float(response.get("y", 0)) - float(target["y"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ScoringError(f"invalid hotspot response or target: {exc}") from exc
    tolerance = float(target.get("tolerance", 0))
    return (dx**2 + dy**2) ** 0.5 <= tolerance


def _grade_image_selection(*, snapshot: dict, response: dict) -> bool:
    return response.get("selected_option_label") in _correct_option_labels(snapshot)


_GRADERS = {
    "single_choice": _grade_single_choice,
    "multiple_choice": _grade_multiple_choice,
    "true_false": _grade_true_false,
    "numeric": _grade_numeric,
    "matching": _grade_matching,
    "ordering": _grade_ordering,
    "hotspot": _grade_hotspot,
    "image_selection": _grade_image_selection,
}


def grade_response(*, exam_question, response: dict) -> tuple[bool, Decimal]:
    """Returns (is_correct, marks_awarded) for an auto-gradable question.
    Raises ScoringError for a subjective type, or a malformed answer key —
    a scoring bug should surface loudly, not silently award 0.
    """
    snapshot = exam_question.snapshot
    if not snapshot:
        raise ScoringError("cannot score a question with no published snapshot yet")
    question_type = snapshot["question_type"]
    grader = _GRADERS.get(question_type)
    if grader is None:
        if question_type in AUTO_GRADABLE_QUESTION_TYPES:
            raise ScoringError(f"no grader implemented for auto-gradable type {question_type!r}")
        raise ScoringError(f"{question_type!r} is not auto-gradable — needs manual grading")
    is_correct = grader(snapshot=snapshot, response=response)
    return is_correct, (exam_question.marks if is_correct else Decimal("0"))
