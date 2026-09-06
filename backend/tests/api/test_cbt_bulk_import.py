"""apps.cbt Phase 8: bulk question import from a flat, spreadsheet-
friendly CSV — single_choice/multiple_choice/true_false only (see
question_service.bulk_import_questions for why richer block/option
content is out of scope for a flat CSV).
"""
import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.cbt.models import Question
from apps.cbt.services.question_service import bulk_import_questions


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.mark.django_db
def test_bulk_import_creates_single_choice_multiple_choice_and_true_false(cbt_fixture_set):
    fs = cbt_fixture_set
    rows = [
        {
            "question_type": "single_choice", "difficulty": "easy", "marks": "2",
            "text": "2+2?", "option_a": "3", "option_b": "4", "correct": "B",
        },
        {
            "question_type": "multiple_choice", "difficulty": "medium", "marks": "5",
            "text": "Which are primes?", "option_a": "2", "option_b": "4", "option_c": "3", "correct": "A,C",
        },
        {
            "question_type": "true_false", "text": "The sky is blue.", "correct": "true",
        },
    ]
    result = bulk_import_questions(
        organization=fs["subject"].organization, actor=None, subject=fs["subject"], class_level=fs["class_level"],
        rows=rows,
    )
    assert result["errors"] == []
    assert len(result["created"]) == 3
    assert Question.objects.count() == 3

    single = result["created"][0]
    assert single.question_type == "single_choice"
    assert single.marks == 2
    assert {o.label: o.is_correct for o in single.options.all()} == {"A": False, "B": True}

    multi = result["created"][1]
    assert {o.label: o.is_correct for o in multi.options.all()} == {"A": True, "B": False, "C": True}

    tf = result["created"][2]
    assert {o.label: o.is_correct for o in tf.options.all()} == {"true": True, "false": False}


@pytest.mark.django_db
def test_bulk_import_collects_per_row_errors_without_aborting(cbt_fixture_set):
    fs = cbt_fixture_set
    rows = [
        {"question_type": "single_choice", "text": "Good row", "option_a": "1", "option_b": "2", "correct": "A"},
        {"question_type": "essay", "text": "Unsupported type"},
        {"question_type": "single_choice", "text": "", "option_a": "1", "option_b": "2", "correct": "A"},
        {"question_type": "single_choice", "text": "Only one option", "option_a": "1", "correct": "A"},
        {"question_type": "single_choice", "text": "Bad correct", "option_a": "1", "option_b": "2", "correct": "Z"},
        {"question_type": "single_choice", "text": "Two correct", "option_a": "1", "option_b": "2", "correct": "A,B"},
        {"question_type": "true_false", "text": "Bad tf correct", "correct": "maybe"},
    ]
    result = bulk_import_questions(
        organization=fs["subject"].organization, actor=None, subject=fs["subject"], class_level=fs["class_level"],
        rows=rows,
    )
    assert len(result["created"]) == 1
    assert len(result["errors"]) == 6
    # 1-based row numbers matching the input list's positions.
    assert [e["row"] for e in result["errors"]] == [2, 3, 4, 5, 6, 7]


@pytest.mark.django_db
def test_bulk_import_resolves_topic_by_name(cbt_fixture_set, cbt_topic_factory):
    fs = cbt_fixture_set
    topic = cbt_topic_factory(subject=fs["subject"], name="Algebra")
    rows = [
        {
            "question_type": "single_choice", "topic": "algebra", "text": "x+1=2, x=?",
            "option_a": "0", "option_b": "1", "correct": "B",
        },
        {
            "question_type": "single_choice", "topic": "Nonexistent Topic", "text": "Bad topic",
            "option_a": "0", "option_b": "1", "correct": "B",
        },
    ]
    result = bulk_import_questions(
        organization=fs["subject"].organization, actor=None, subject=fs["subject"], class_level=fs["class_level"],
        rows=rows,
    )
    assert len(result["created"]) == 1
    assert result["created"][0].topic_id == topic.id
    assert len(result["errors"]) == 1
    assert "Nonexistent Topic" in result["errors"][0]["error"]


@pytest.mark.django_db
def test_bulk_import_endpoint_requires_permission_and_returns_created_and_errors(
    api_client, organization, user_factory, cbt_fixture_set
):
    from django.core.files.uploadedfile import SimpleUploadedFile

    fs = cbt_fixture_set
    csv_content = (
        "question_type,text,option_a,option_b,correct\n"
        "single_choice,2+2?,3,4,B\n"
        "single_choice,,3,4,B\n"
    )

    norole = user_factory(organization=organization, email="norole@example.com", password="s3cret-pass!")
    _login(api_client, "norole@example.com", "s3cret-pass!")
    upload = SimpleUploadedFile("questions.csv", csv_content.encode(), content_type="text/csv")
    denied = api_client.post(
        "/api/v1/cbt/questions/bulk-import",
        {"file": upload, "subject": str(fs["subject"].public_id), "class_level": str(fs["class_level"].public_id)},
        format="multipart",
    )
    assert denied.status_code == 403

    user = user_factory(organization=organization, email="admin@example.com", password="s3cret-pass!")
    _grant(user, "cbt_questions.create")
    _login(api_client, "admin@example.com", "s3cret-pass!")

    upload = SimpleUploadedFile("questions.csv", csv_content.encode(), content_type="text/csv")
    resp = api_client.post(
        "/api/v1/cbt/questions/bulk-import",
        {"file": upload, "subject": str(fs["subject"].public_id), "class_level": str(fs["class_level"].public_id)},
        format="multipart",
    )
    assert resp.status_code == 201, resp.json()
    data = resp.json()["data"]
    assert data["created_count"] == 1
    assert data["error_count"] == 1
    assert data["errors"][0]["row"] == 2
    assert Question.objects.count() == 1
