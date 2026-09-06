"""apps.cbt Phase 3: assembling published/approved bank questions
(Phase 1/2) into a deliverable, immutably-snapshotted exam with assigned
candidates. No attempts/timer/scoring yet — that's Phase 4 — so these
tests call exam_service directly, mirroring how Phase 1's
test_cbt_questions.py exercises question_service before the API existed.
"""
import pytest

from apps.cbt.models import CBTExam, ExamCandidate, ExamQuestion
from apps.cbt.services.exam_service import (
    ExamError,
    InvalidExamTransition,
    add_candidate,
    add_candidates_from_class_arm,
    add_question_to_exam,
    archive_exam,
    create_exam,
    generate_questions_for_exam,
    publish_exam,
    remove_question_from_exam,
    reorder_exam_questions,
)
from apps.cbt.services.question_service import approve_question, submit_question
from apps.tenancy.context import activate_organization


def _approved_question(cbt_question_factory, fs, **extra):
    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"], **extra)
    submit_question(question=question, actor=None)
    approve_question(question=question, actor=None)
    return question


@pytest.mark.django_db
def test_create_exam_auto_generates_code(cbt_exam_fixture_set):
    fs = cbt_exam_fixture_set
    exam = create_exam(
        organization=fs["school"].organization,
        actor=None,
        school=fs["school"],
        academic_year=fs["academic_year"],
        term=fs["term"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        name="First CA",
        exam_type="ca",
        duration_minutes=30,
        pass_mark="20.00",
        start_at="2025-09-15T09:00:00Z",
        end_at="2025-09-15T09:30:00Z",
    )
    assert exam.code.startswith("CBT-")
    assert exam.status == "draft"
    assert exam.total_marks == 0


@pytest.mark.django_db
def test_add_question_requires_approved_or_published_status(cbt_exam_fixture_set, cbt_question_factory):
    fs = cbt_exam_fixture_set
    draft_question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"])

    with pytest.raises(ExamError):
        add_question_to_exam(exam=fs["exam"], question=draft_question)

    approved = _approved_question(cbt_question_factory, fs)
    exam_question = add_question_to_exam(exam=fs["exam"], question=approved)
    assert exam_question.order == 1
    assert exam_question.snapshot == {}


@pytest.mark.django_db
def test_add_question_rejected_on_non_draft_exam(cbt_exam_fixture_set, cbt_question_factory, student_factory):
    fs = cbt_exam_fixture_set
    q1 = _approved_question(cbt_question_factory, fs)
    add_question_to_exam(exam=fs["exam"], question=q1)
    add_candidate(exam=fs["exam"], student=student_factory(school=fs["school"]))
    publish_exam(exam=fs["exam"], actor=None)

    q2 = _approved_question(cbt_question_factory, fs)
    with pytest.raises(ExamError):
        add_question_to_exam(exam=fs["exam"], question=q2)


@pytest.mark.django_db
def test_reorder_exam_questions(cbt_exam_fixture_set, cbt_question_factory):
    fs = cbt_exam_fixture_set
    q1 = add_question_to_exam(exam=fs["exam"], question=_approved_question(cbt_question_factory, fs))
    q2 = add_question_to_exam(
        exam=fs["exam"], question=_approved_question(cbt_question_factory, fs)
    )
    assert q1.order == 1
    assert q2.order == 2

    reorder_exam_questions(exam=fs["exam"], ordered_public_ids=[str(q2.public_id), str(q1.public_id)])

    q1.refresh_from_db()
    q2.refresh_from_db()
    assert q2.order == 1
    assert q1.order == 2


@pytest.mark.django_db
def test_reorder_rejects_incomplete_or_mismatched_id_set(cbt_exam_fixture_set, cbt_question_factory):
    fs = cbt_exam_fixture_set
    add_question_to_exam(exam=fs["exam"], question=_approved_question(cbt_question_factory, fs))

    with pytest.raises(ExamError):
        reorder_exam_questions(exam=fs["exam"], ordered_public_ids=[])


@pytest.mark.django_db
def test_remove_question_from_draft_exam(cbt_exam_fixture_set, cbt_question_factory):
    fs = cbt_exam_fixture_set
    exam_question = add_question_to_exam(exam=fs["exam"], question=_approved_question(cbt_question_factory, fs))

    remove_question_from_exam(exam_question=exam_question)

    assert ExamQuestion.objects.filter(exam=fs["exam"]).count() == 0


@pytest.mark.django_db
def test_generate_questions_respects_difficulty_distribution(cbt_exam_fixture_set, cbt_question_factory):
    fs = cbt_exam_fixture_set
    for i in range(4):
        _approved_question(cbt_question_factory, fs, difficulty="easy")
    for i in range(4):
        _approved_question(cbt_question_factory, fs, difficulty="hard")

    created = generate_questions_for_exam(
        exam=fs["exam"],
        subject=fs["subject"],
        class_level=fs["class_level"],
        count=4,
        difficulty_distribution={"easy": 50, "hard": 50},
    )

    assert len(created) == 4
    difficulties = [eq.question.difficulty for eq in created]
    assert difficulties.count("easy") == 2
    assert difficulties.count("hard") == 2
    # Orders are contiguous and start at 1 on a fresh exam.
    assert sorted(eq.order for eq in created) == [1, 2, 3, 4]


@pytest.mark.django_db
def test_generate_questions_raises_when_bank_is_empty(cbt_exam_fixture_set):
    fs = cbt_exam_fixture_set
    with pytest.raises(ExamError):
        generate_questions_for_exam(
            exam=fs["exam"], subject=fs["subject"], class_level=fs["class_level"], count=5
        )


@pytest.mark.django_db
def test_add_candidates_from_class_arm_is_idempotent(
    cbt_exam_fixture_set, student_factory, enrollment_factory
):
    fs = cbt_exam_fixture_set
    student = student_factory(school=fs["school"])
    enrollment_factory(student=student, class_arm=fs["class_arm"], academic_year=fs["academic_year"])

    first = add_candidates_from_class_arm(
        exam=fs["exam"], class_arm=fs["class_arm"], academic_year=fs["academic_year"]
    )
    second = add_candidates_from_class_arm(
        exam=fs["exam"], class_arm=fs["class_arm"], academic_year=fs["academic_year"]
    )

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].pk == second[0].pk
    assert ExamCandidate.objects.filter(exam=fs["exam"]).count() == 1
    assert first[0].candidate_number.startswith(fs["exam"].code)


@pytest.mark.django_db
def test_publish_requires_questions_and_candidates(cbt_exam_fixture_set, cbt_question_factory, student_factory):
    fs = cbt_exam_fixture_set

    with pytest.raises(ExamError):
        publish_exam(exam=fs["exam"], actor=None)

    add_question_to_exam(exam=fs["exam"], question=_approved_question(cbt_question_factory, fs))
    with pytest.raises(ExamError):
        publish_exam(exam=fs["exam"], actor=None)

    add_candidate(exam=fs["exam"], student=student_factory(school=fs["school"]))
    published = publish_exam(exam=fs["exam"], actor=None)
    assert published.status == "published"


@pytest.mark.django_db
def test_publish_snapshots_questions_and_computes_total_marks(
    cbt_exam_fixture_set, cbt_question_factory, student_factory
):
    from apps.cbt.models import QuestionBlock

    fs = cbt_exam_fixture_set
    q1 = _approved_question(cbt_question_factory, fs, marks="5.00")
    QuestionBlock.objects.create(
        organization=q1.organization, question=q1, block_type="paragraph", content={"html": "Q1"}, order=1
    )
    q2 = _approved_question(cbt_question_factory, fs, marks="3.00")

    eq1 = add_question_to_exam(exam=fs["exam"], question=q1)
    add_question_to_exam(exam=fs["exam"], question=q2, marks_override="10.00")
    add_candidate(exam=fs["exam"], student=student_factory(school=fs["school"]))

    published = publish_exam(exam=fs["exam"], actor=None)

    assert published.total_marks == pytest.approx(15.00)  # 5.00 + 10.00 override
    eq1.refresh_from_db()
    assert eq1.snapshot["blocks"][0]["content"]["html"] == "Q1"
    assert eq1.snapshot["marks"] == "5.00"


@pytest.mark.django_db
def test_publish_rejects_start_after_end(cbt_exam_fixture_set, cbt_question_factory, student_factory):
    fs = cbt_exam_fixture_set
    fs["exam"].start_at = "2025-09-15T10:00:00Z"
    fs["exam"].end_at = "2025-09-15T09:00:00Z"
    fs["exam"].save(update_fields=["start_at", "end_at"])

    add_question_to_exam(exam=fs["exam"], question=_approved_question(cbt_question_factory, fs))
    add_candidate(exam=fs["exam"], student=student_factory(school=fs["school"]))

    with pytest.raises(ExamError):
        publish_exam(exam=fs["exam"], actor=None)


@pytest.mark.django_db
def test_cannot_publish_twice_or_archive_a_draft(cbt_exam_fixture_set, cbt_question_factory, student_factory):
    fs = cbt_exam_fixture_set
    add_question_to_exam(exam=fs["exam"], question=_approved_question(cbt_question_factory, fs))
    add_candidate(exam=fs["exam"], student=student_factory(school=fs["school"]))

    with pytest.raises(InvalidExamTransition):
        archive_exam(exam=fs["exam"], actor=None)

    publish_exam(exam=fs["exam"], actor=None)
    with pytest.raises(InvalidExamTransition):
        publish_exam(exam=fs["exam"], actor=None)

    archived = archive_exam(exam=fs["exam"], actor=None)
    assert archived.status == "archived"


@pytest.mark.django_db
def test_cbt_exam_tenant_isolation(cbt_exam_fixture_set, other_organization):
    fs = cbt_exam_fixture_set

    activate_organization(other_organization.id)
    try:
        assert CBTExam.objects.count() == 0
    finally:
        activate_organization(fs["school"].organization_id)

    assert CBTExam.objects.count() == 1
