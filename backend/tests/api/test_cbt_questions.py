"""apps.cbt Phase 1: the question bank's rich-content model and its
authoring workflow (create -> submit -> review -> approve -> publish,
versioning on edit-after-publish, duplication). No DRF endpoints yet —
those are Phase 2 — so these tests call the service layer directly, the
same way apps.report_cards' generate_report_card tests exercise
report_card_service before that app had a full API surface either.
"""
import pytest

from apps.cbt.models import Question, QuestionBlock, QuestionOption, QuestionVersion
from apps.cbt.services.question_service import (
    InvalidQuestionTransition,
    QuestionError,
    approve_question,
    create_question,
    duplicate_question,
    publish_question,
    reject_question,
    submit_question,
    update_question,
    upload_media,
    validate_block_content,
)
from apps.tenancy.context import activate_organization


@pytest.mark.django_db
def test_create_question_with_blocks_and_options(cbt_fixture_set):
    fs = cbt_fixture_set
    question = create_question(
        organization=fs["subject"].organization,
        actor=None,
        subject=fs["subject"],
        class_level=fs["class_level"],
        question_type="single_choice",
        marks="5.00",
        blocks=[
            {"block_type": "paragraph", "content": {"html": "<p>Calculate the total resistance.</p>"}, "order": 1},
            {"block_type": "equation", "content": {"latex": "R_T = R_1 + R_2"}, "order": 2},
        ],
        options=[
            {"label": "A", "content": {"html": "5"}, "is_correct": False, "order": 1},
            {"label": "B", "content": {"html": "10"}, "is_correct": True, "order": 2},
        ],
    )

    assert question.code.startswith("Q-")
    assert question.status == "draft"
    assert question.blocks.count() == 2
    assert list(question.blocks.values_list("block_type", flat=True)) == ["paragraph", "equation"]
    assert question.options.count() == 2
    assert question.options.get(label="B").is_correct is True


@pytest.mark.django_db
def test_question_codes_increment_per_organization(cbt_fixture_set):
    fs = cbt_fixture_set
    q1 = create_question(
        organization=fs["subject"].organization, actor=None, subject=fs["subject"],
        class_level=fs["class_level"], question_type="numeric", marks="2.00",
    )
    q2 = create_question(
        organization=fs["subject"].organization, actor=None, subject=fs["subject"],
        class_level=fs["class_level"], question_type="numeric", marks="2.00",
    )
    assert q1.code != q2.code
    assert int(q2.code.split("-")[1]) == int(q1.code.split("-")[1]) + 1


@pytest.mark.django_db
def test_validate_block_content_rejects_missing_required_key():
    with pytest.raises(QuestionError):
        validate_block_content(block_type="equation", content={})
    validate_block_content(block_type="equation", content={"latex": "x^2"})


@pytest.mark.django_db
def test_validate_block_content_rejects_unknown_block_type():
    with pytest.raises(QuestionError):
        validate_block_content(block_type="not_a_real_block", content={})


@pytest.mark.django_db
def test_create_question_rejects_invalid_block_content(cbt_fixture_set):
    fs = cbt_fixture_set
    with pytest.raises(QuestionError):
        create_question(
            organization=fs["subject"].organization, actor=None, subject=fs["subject"],
            class_level=fs["class_level"], question_type="single_choice", marks="1.00",
            blocks=[{"block_type": "image", "content": {}, "order": 1}],
        )
    # The whole create is transactional — a bad block must not leave a
    # half-created Question behind.
    assert Question.all_tenants.count() == 0


@pytest.mark.django_db
def test_question_workflow_happy_path(cbt_question_factory, cbt_fixture_set, user_factory):
    fs = cbt_fixture_set
    reviewer = user_factory(organization=fs["subject"].organization, email="reviewer@example.com")
    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"])

    submit_question(question=question, actor=None)
    assert question.status == "submitted"

    from apps.cbt.services.question_service import start_review

    start_review(question=question, actor=None)
    assert question.status == "review"

    approve_question(question=question, actor=reviewer)
    assert question.status == "approved"
    assert question.approved_by == reviewer

    publish_question(question=question, actor=None)
    assert question.status == "published"


@pytest.mark.django_db
def test_invalid_transition_is_rejected(cbt_question_factory, cbt_fixture_set):
    fs = cbt_fixture_set
    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"])

    with pytest.raises(InvalidQuestionTransition):
        publish_question(question=question, actor=None)
    assert question.status == "draft"


@pytest.mark.django_db
def test_reject_sends_question_back_to_draft_and_clears_approval(cbt_question_factory, cbt_fixture_set):
    fs = cbt_fixture_set
    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"])
    submit_question(question=question, actor=None)

    reject_question(question=question, actor=None)

    question.refresh_from_db()
    assert question.status == "draft"
    assert question.approved_by is None


@pytest.mark.django_db
def test_editing_a_published_question_snapshots_a_version_first(cbt_question_factory, cbt_fixture_set):
    fs = cbt_fixture_set
    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"], marks="5.00")
    QuestionBlock.objects.create(
        organization=question.organization, question=question,
        block_type="paragraph", content={"html": "original"}, order=1,
    )
    submit_question(question=question, actor=None)
    from apps.cbt.services.question_service import start_review

    start_review(question=question, actor=None)
    approve_question(question=question, actor=None)
    publish_question(question=question, actor=None)

    assert QuestionVersion.objects.count() == 0

    update_question(
        question=question, actor=None, marks="7.00",
        blocks=[{"block_type": "paragraph", "content": {"html": "revised"}, "order": 1}],
    )

    assert QuestionVersion.objects.count() == 1
    version = QuestionVersion.objects.get()
    assert version.version_number == 1
    assert version.content["marks"] == "5.00"
    assert version.content["blocks"][0]["content"]["html"] == "original"

    question.refresh_from_db()
    assert question.marks == pytest.approx(7.00)
    assert question.status == "published"
    assert question.blocks.get().content["html"] == "revised"


@pytest.mark.django_db
def test_editing_a_draft_question_does_not_snapshot(cbt_question_factory, cbt_fixture_set):
    fs = cbt_fixture_set
    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"])

    update_question(question=question, actor=None, marks="9.00")

    assert QuestionVersion.objects.count() == 0
    question.refresh_from_db()
    assert question.marks == pytest.approx(9.00)


@pytest.mark.django_db
def test_duplicate_question_is_an_independent_draft_copy(cbt_question_factory, cbt_fixture_set):
    fs = cbt_fixture_set
    question = cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"], marks="3.00")
    QuestionOption.objects.create(
        organization=question.organization, question=question,
        label="A", content={"html": "yes"}, is_correct=True, order=1,
    )
    submit_question(question=question, actor=None)

    copy = duplicate_question(question=question, actor=None)

    assert copy.pk != question.pk
    assert copy.code != question.code
    assert copy.status == "draft"
    assert copy.options.count() == 1
    assert copy.options.get().label == "A"

    # Editing the copy must never touch the original.
    copy.options.get().delete()
    assert question.options.count() == 1


@pytest.mark.django_db
def test_upload_media_stores_an_image_and_records_its_metadata(cbt_fixture_set):
    fs = cbt_fixture_set
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 20

    media = upload_media(
        organization=fs["subject"].organization,
        actor=None,
        name="Circuit diagram",
        media_type="image",
        file_name="circuit.png",
        content=png_bytes,
        content_type="image/png",
    )

    assert media.storage_key
    assert media.size_bytes == len(png_bytes)
    assert media.media_type == "image"


@pytest.mark.django_db
def test_question_tenant_isolation(cbt_fixture_set, other_organization, cbt_question_factory):
    fs = cbt_fixture_set
    cbt_question_factory(subject=fs["subject"], class_level=fs["class_level"])

    activate_organization(other_organization.id)
    try:
        assert Question.objects.count() == 0
    finally:
        activate_organization(fs["subject"].organization_id)

    assert Question.objects.count() == 1
