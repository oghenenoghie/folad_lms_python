"""Scores one StudentAnswer's `response` against its ExamQuestion's frozen
`snapshot` (never the live Question — see ExamQuestion.marks' docstring on
why: the attempt is scored against exactly what the candidate was shown,
not whatever the bank question has become since). Covers every
AUTO_GRADABLE_QUESTION_TYPES entry; a subjective type is never graded
here — see apps.cbt.services.attempt_service.grade_subjective_answer.
"""
from decimal import Decimal, InvalidOperation
import math

from apps.cbt.models import AUTO_GRADABLE_QUESTION_TYPES


class ScoringError(ValueError):
    pass


def _correct_option_labels(snapshot: dict) -> set[str]:
    return {o["label"] for o in snapshot["options"] if o["is_correct"]}


def _grade_single_choice(*, snapshot: dict, response: dict) -> bool:
    selected = response.get("selected_option_label")
    return isinstance(selected, str) and selected in _correct_option_labels(snapshot)


def _grade_multiple_choice(*, snapshot: dict, response: dict) -> bool:
    selected = response.get("selected_option_labels", [])
    if not isinstance(selected, list) or any(not isinstance(label, str) for label in selected):
        return False
    return set(selected) == _correct_option_labels(snapshot)


def _grade_true_false(*, snapshot: dict, response: dict) -> bool:
    selected = response.get("selected_option_label")
    return isinstance(selected, str) and selected in _correct_option_labels(snapshot)


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
        tolerance = Decimal(str(key.get("tolerance", 0)))
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        raise ScoringError(f"invalid numeric answer key: {exc}") from exc
    if not expected.is_finite() or not tolerance.is_finite() or tolerance < 0:
        raise ScoringError("numeric answer key and tolerance must be finite; tolerance cannot be negative")

    try:
        given = Decimal(str(response.get("value")))
    except (TypeError, ValueError, ArithmeticError):
        return False
    if not given.is_finite():
        return False
    try:
        return abs(given - expected) <= tolerance
    except InvalidOperation:
        return False


def _grade_matching(*, snapshot: dict, response: dict) -> bool:
    """The correct mapping lives in the first option's `content` (e.g.
    `{"matches": {"A": "3", "B": "1"}}`)."""
    if not snapshot["options"]:
        raise ScoringError("matching question has no configured answer key")
    expected = snapshot["options"][0]["content"].get("matches", {})
    if not isinstance(expected, dict):
        raise ScoringError("matching answer key must be an object")
    submitted = response.get("matches", {})
    return isinstance(submitted, dict) and submitted == expected


def _grade_ordering(*, snapshot: dict, response: dict) -> bool:
    """The correct sequence lives in the first option's `content` (e.g.
    `{"sequence": ["3", "1", "2"]}`)."""
    if not snapshot["options"]:
        raise ScoringError("ordering question has no configured answer key")
    expected = snapshot["options"][0]["content"].get("sequence", [])
    if not isinstance(expected, list):
        raise ScoringError("ordering answer key must be a list")
    submitted = response.get("sequence", [])
    return isinstance(submitted, list) and submitted == expected


def _grade_hotspot(*, snapshot: dict, response: dict) -> bool:
    """The target region lives in the first option's `content` (e.g.
    `{"x": 432, "y": 271, "tolerance": 20}`) — a click within `tolerance`
    pixels of the target counts."""
    if not snapshot["options"]:
        raise ScoringError("hotspot question has no configured answer key")
    target = snapshot["options"][0]["content"]
    try:
        target_x = float(target["x"])
        target_y = float(target["y"])
        tolerance = float(target.get("tolerance", 0))
    except (KeyError, TypeError, ValueError) as exc:
        raise ScoringError(f"invalid hotspot answer key: {exc}") from exc
    if not all(math.isfinite(value) for value in (target_x, target_y, tolerance)) or tolerance < 0:
        raise ScoringError("hotspot answer key coordinates and tolerance must be finite and tolerance non-negative")

    try:
        answer_x = float(response.get("x"))
        answer_y = float(response.get("y"))
    except (TypeError, ValueError):
        return False
    if not math.isfinite(answer_x) or not math.isfinite(answer_y):
        return False
    dx = answer_x - target_x
    dy = answer_y - target_y
    return math.hypot(dx, dy) <= tolerance


def _grade_image_selection(*, snapshot: dict, response: dict) -> bool:
    selected = response.get("selected_option_label")
    return isinstance(selected, str) and selected in _correct_option_labels(snapshot)


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
    exam = getattr(exam_question, "exam", None)
    negative_marking = bool(getattr(exam, "negative_marking", False))
    penalty = Decimal("0")
    if negative_marking:
        try:
            penalty = Decimal(str(snapshot.get("negative_marks", "0")))
        except (TypeError, ValueError, ArithmeticError) as exc:
            raise ScoringError(f"invalid negative_marks in frozen question snapshot: {exc}") from exc
        if not penalty.is_finite() or penalty < 0 or penalty > exam_question.marks:
            raise ScoringError("negative_marks must be finite and between zero and the question's marks")

    # Empty/blank responses are unanswered, not wrong answers. This also
    # covers StudentAnswer rows created solely to flag a question. Check
    # before calling the type-specific grader: malformed non-blank values
    # are treated as incorrect answers, but an empty response must remain
    # an ordinary unanswered item.
    has_response = any(
        value is not None
        and not (isinstance(value, str) and not value.strip())
        and value != []
        and value != {}
        for value in (response or {}).values()
    )
    if not has_response:
        return False, Decimal("0")

    is_correct = grader(snapshot=snapshot, response=response)
    if is_correct:
        return True, exam_question.marks
    return False, -penalty if negative_marking else Decimal("0")