"""Pure logic tests for apps.cbt.services.scoring_service — no DB needed
beyond building a plain snapshot dict, since grade_response only ever
reads a frozen ExamQuestion.snapshot, never the live Question.
"""
import pytest

from apps.cbt.services.scoring_service import ScoringError, grade_response


class _FakeExamQuestion:
    def __init__(self, snapshot, marks="5.00"):
        from decimal import Decimal

        self.snapshot = snapshot
        self.marks = Decimal(marks)


def _snapshot(question_type, options=None):
    return {"question_type": question_type, "options": options or []}


def test_single_choice_correct_and_incorrect():
    snapshot = _snapshot(
        "single_choice",
        [{"label": "A", "is_correct": False}, {"label": "B", "is_correct": True}],
    )
    eq = _FakeExamQuestion(snapshot)

    correct, marks = grade_response(exam_question=eq, response={"selected_option_label": "B"})
    assert correct is True
    assert marks == eq.marks

    wrong, zero = grade_response(exam_question=eq, response={"selected_option_label": "A"})
    assert wrong is False
    assert zero == 0


def test_multiple_choice_requires_exact_set_match():
    snapshot = _snapshot(
        "multiple_choice",
        [
            {"label": "A", "is_correct": True},
            {"label": "B", "is_correct": True},
            {"label": "C", "is_correct": False},
        ],
    )
    eq = _FakeExamQuestion(snapshot)

    correct, _ = grade_response(exam_question=eq, response={"selected_option_labels": ["A", "B"]})
    assert correct is True

    partial, _ = grade_response(exam_question=eq, response={"selected_option_labels": ["A"]})
    assert partial is False

    extra, _ = grade_response(exam_question=eq, response={"selected_option_labels": ["A", "B", "C"]})
    assert extra is False


def test_numeric_within_tolerance():
    snapshot = _snapshot("numeric", [{"content": {"value": 42, "tolerance": 0.5}}])
    eq = _FakeExamQuestion(snapshot)

    close, _ = grade_response(exam_question=eq, response={"value": 42.3})
    assert close is True

    far, _ = grade_response(exam_question=eq, response={"value": 43})
    assert far is False


def test_numeric_missing_answer_key_raises():
    eq = _FakeExamQuestion(_snapshot("numeric", []))
    with pytest.raises(ScoringError):
        grade_response(exam_question=eq, response={"value": 1})


def test_matching_exact_dict_match():
    snapshot = _snapshot("matching", [{"content": {"matches": {"A": "3", "B": "1"}}}])
    eq = _FakeExamQuestion(snapshot)

    correct, _ = grade_response(exam_question=eq, response={"matches": {"A": "3", "B": "1"}})
    assert correct is True

    wrong, _ = grade_response(exam_question=eq, response={"matches": {"A": "1", "B": "3"}})
    assert wrong is False


def test_ordering_exact_sequence_match():
    snapshot = _snapshot("ordering", [{"content": {"sequence": ["3", "1", "2"]}}])
    eq = _FakeExamQuestion(snapshot)

    correct, _ = grade_response(exam_question=eq, response={"sequence": ["3", "1", "2"]})
    assert correct is True

    wrong, _ = grade_response(exam_question=eq, response={"sequence": ["1", "2", "3"]})
    assert wrong is False


def test_hotspot_within_pixel_tolerance():
    snapshot = _snapshot("hotspot", [{"content": {"x": 100, "y": 100, "tolerance": 10}}])
    eq = _FakeExamQuestion(snapshot)

    correct, _ = grade_response(exam_question=eq, response={"x": 105, "y": 103})
    assert correct is True

    wrong, _ = grade_response(exam_question=eq, response={"x": 200, "y": 200})
    assert wrong is False


def test_true_false_and_image_selection_use_correct_option_label():
    tf = _FakeExamQuestion(_snapshot("true_false", [{"label": "true", "is_correct": True}]))
    correct, _ = grade_response(exam_question=tf, response={"selected_option_label": "true"})
    assert correct is True

    img = _FakeExamQuestion(_snapshot("image_selection", [{"label": "img2", "is_correct": True}]))
    correct2, _ = grade_response(exam_question=img, response={"selected_option_label": "img2"})
    assert correct2 is True


def test_subjective_type_raises_scoring_error():
    eq = _FakeExamQuestion(_snapshot("short_answer", []))
    with pytest.raises(ScoringError):
        grade_response(exam_question=eq, response={"text": "an essay answer"})


def test_no_snapshot_raises_scoring_error():
    eq = _FakeExamQuestion(snapshot=None)
    with pytest.raises(ScoringError):
        grade_response(exam_question=eq, response={})
