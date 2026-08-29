import pytest
from django.db import ProgrammingError, connection, transaction

from apps.accounts.models import Permission, Role, RolePermission, UserRole
from apps.finance.models import Invoice, LedgerEntry
from apps.tenancy.context import activate_organization


def _grant(user, *codes):
    role = Role.objects.create(name=f"ROLE_{user.pk}_{'_'.join(codes)}"[:100], label="Test Role")
    for code in codes:
        RolePermission.objects.create(role=role, permission=Permission.objects.get(code=code))
    UserRole.objects.create(user=user, role=role)


def _login(api_client, email, password):
    resp = api_client.post("/api/v1/auth/login", {"email": email, "password": password}, format="json")
    token = resp.json()["data"]["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


@pytest.fixture
def finance_fixture_set(organization, school_factory, academic_year_factory, term_factory, student_factory):
    school = school_factory(organization=organization)
    academic_year = academic_year_factory(school=school)
    term = term_factory(academic_year=academic_year)
    student = student_factory(school=school)
    return {"school": school, "academic_year": academic_year, "term": term, "student": student}


def _issued_invoice(api_client, finance_fixture_set, fee_structure_factory, fee_item_factory):
    term = finance_fixture_set["term"]
    student = finance_fixture_set["student"]
    fee_structure = fee_structure_factory(term=term)
    fee_item_factory(fee_structure=fee_structure, name="Tuition", amount_minor=500_000)

    create = api_client.post(
        "/api/v1/invoices",
        {
            "student": str(student.public_id),
            "term": str(term.public_id),
            "invoice_number": "INV-1001",
        },
        format="json",
    )
    assert create.status_code == 201
    invoice_public_id = create.json()["data"]["public_id"]

    fee_item_public_id = fee_structure.items.get(name="Tuition").public_id
    add_line = api_client.post(
        "/api/v1/invoice-lines",
        {"invoice": invoice_public_id, "fee_item": str(fee_item_public_id)},
        format="json",
    )
    assert add_line.status_code == 201

    issue = api_client.post(f"/api/v1/invoices/{invoice_public_id}/issue")
    assert issue.status_code == 200, issue.json()
    assert issue.json()["data"]["status"] == "issued"
    assert issue.json()["data"]["total_minor"] == 500_000
    return invoice_public_id


@pytest.mark.django_db
def test_invoice_lifecycle_issue_posts_balanced_ledger_entries(
    api_client, organization, user_factory, finance_fixture_set, fee_structure_factory, fee_item_factory,
):
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(
        user, "invoices.view", "invoices.create", "invoices.issue",
        "invoice_lines.view", "invoice_lines.create", "ledger_entries.view",
    )
    _login(api_client, "a@example.com", "s3cret-pass!")

    _issued_invoice(api_client, finance_fixture_set, fee_structure_factory, fee_item_factory)

    ledger = api_client.get("/api/v1/ledger-entries?ref_type=invoice")
    entries = ledger.json()["data"]["results"]
    assert len(entries) == 2
    assert sum(e["debit_minor"] for e in entries) == sum(e["credit_minor"] for e in entries) == 500_000
    accounts = {e["account"] for e in entries}
    assert accounts == {"accounts_receivable", "revenue"}


@pytest.mark.django_db
def test_invoice_lines_locked_once_issued(
    api_client, organization, user_factory, finance_fixture_set, fee_structure_factory, fee_item_factory,
):
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(
        user, "invoices.view", "invoices.create", "invoices.issue",
        "invoice_lines.view", "invoice_lines.create", "invoice_lines.update",
    )
    _login(api_client, "a@example.com", "s3cret-pass!")

    invoice_public_id = _issued_invoice(api_client, finance_fixture_set, fee_structure_factory, fee_item_factory)

    blocked = api_client.post(
        "/api/v1/invoice-lines",
        {"invoice": invoice_public_id, "description": "Extra charge", "unit_amount_minor": 1000},
        format="json",
    )
    assert blocked.status_code == 409


# transaction=True: payment_service enqueues the receipt task via
# transaction.on_commit(), which never fires under the default rollback-only
# django_db fixture — this test needs a real commit to observe it.
@pytest.mark.django_db(transaction=True)
def test_record_payment_partial_then_full_updates_invoice_status(
    api_client, organization, user_factory, finance_fixture_set, fee_structure_factory, fee_item_factory,
):
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(
        user, "invoices.view", "invoices.create", "invoices.issue",
        "invoice_lines.view", "invoice_lines.create", "payments.view", "payments.create", "receipts.view",
    )
    _login(api_client, "a@example.com", "s3cret-pass!")

    invoice_public_id = _issued_invoice(api_client, finance_fixture_set, fee_structure_factory, fee_item_factory)

    partial = api_client.post(
        "/api/v1/payments",
        {"invoice": invoice_public_id, "reference": "PAY-1", "amount_minor": 200_000, "method": "cash"},
        format="json",
    )
    assert partial.status_code == 201
    payment_public_id = partial.json()["data"]["public_id"]

    invoice_after_partial = api_client.get(f"/api/v1/invoices/{invoice_public_id}")
    assert invoice_after_partial.json()["data"]["status"] == "partially_paid"

    # CELERY_TASK_ALWAYS_EAGER runs the receipt task synchronously above.
    receipts = api_client.get(f"/api/v1/receipts?payment_id={payment_public_id}")
    receipt = receipts.json()["data"]["results"][0]
    assert receipt["status"] == "ready"
    assert receipt["file_url"]

    full = api_client.post(
        "/api/v1/payments",
        {"invoice": invoice_public_id, "reference": "PAY-2", "amount_minor": 300_000, "method": "bank_transfer"},
        format="json",
    )
    assert full.status_code == 201

    invoice_after_full = api_client.get(f"/api/v1/invoices/{invoice_public_id}")
    assert invoice_after_full.json()["data"]["status"] == "paid"


@pytest.mark.django_db
def test_payment_rejects_duplicate_reference_and_overpayment(
    api_client, organization, user_factory, finance_fixture_set, fee_structure_factory, fee_item_factory,
):
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(
        user, "invoices.view", "invoices.create", "invoices.issue",
        "invoice_lines.view", "invoice_lines.create", "payments.create",
    )
    _login(api_client, "a@example.com", "s3cret-pass!")

    invoice_public_id = _issued_invoice(api_client, finance_fixture_set, fee_structure_factory, fee_item_factory)

    payload = {"invoice": invoice_public_id, "reference": "DUPLICATE-REF", "amount_minor": 100_000, "method": "cash"}
    first = api_client.post("/api/v1/payments", payload, format="json")
    assert first.status_code == 201

    duplicate = api_client.post("/api/v1/payments", {**payload, "amount_minor": 50_000}, format="json")
    assert duplicate.status_code == 409

    overpay = api_client.post(
        "/api/v1/payments",
        {"invoice": invoice_public_id, "reference": "OVERPAY", "amount_minor": 10_000_000, "method": "cash"},
        format="json",
    )
    assert overpay.status_code == 409


@pytest.mark.django_db
def test_refund_reverses_payment_and_ledger(
    api_client, organization, user_factory, finance_fixture_set, fee_structure_factory, fee_item_factory,
):
    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(
        user, "invoices.view", "invoices.create", "invoices.issue",
        "invoice_lines.view", "invoice_lines.create", "payments.create",
        "refunds.view", "refunds.create", "ledger_entries.view",
    )
    _login(api_client, "a@example.com", "s3cret-pass!")

    invoice_public_id = _issued_invoice(api_client, finance_fixture_set, fee_structure_factory, fee_item_factory)

    payment = api_client.post(
        "/api/v1/payments",
        {"invoice": invoice_public_id, "reference": "PAY-FULL", "amount_minor": 500_000, "method": "cash"},
        format="json",
    )
    payment_public_id = payment.json()["data"]["public_id"]
    assert api_client.get(f"/api/v1/invoices/{invoice_public_id}").json()["data"]["status"] == "paid"

    refund = api_client.post(
        "/api/v1/refunds",
        {"payment": payment_public_id, "amount_minor": 200_000, "reason": "Overcharged"},
        format="json",
    )
    assert refund.status_code == 201

    invoice_after_refund = api_client.get(f"/api/v1/invoices/{invoice_public_id}")
    assert invoice_after_refund.json()["data"]["status"] == "partially_paid"

    ledger = api_client.get("/api/v1/ledger-entries?ref_type=refund")
    entries = ledger.json()["data"]["results"]
    assert len(entries) == 2
    assert {e["account"] for e in entries} == {"accounts_receivable", "cash"}

    over_refund = api_client.post(
        "/api/v1/refunds",
        {"payment": payment_public_id, "amount_minor": 400_000, "reason": "Too much"},
        format="json",
    )
    assert over_refund.status_code == 409


@pytest.mark.django_db
def test_finance_app_layer_tenant_isolation(
    organization, other_organization, school_factory, academic_year_factory, term_factory, student_factory,
    invoice_factory,
):
    school_a = school_factory(organization=organization)
    school_b = school_factory(organization=other_organization)
    term_a = term_factory(academic_year=academic_year_factory(school=school_a))
    term_b = term_factory(academic_year=academic_year_factory(school=school_b))
    student_a = student_factory(school=school_a)
    student_b = student_factory(school=school_b)
    invoice_factory(student=student_a, term=term_a, invoice_number="A-1")
    invoice_factory(student=student_b, term=term_b, invoice_number="B-1")

    activate_organization(organization.id)
    visible = Invoice.objects.all()

    assert visible.count() == 1
    assert visible.first().organization_id == organization.id


@pytest.mark.skipif(connection.vendor != "postgresql", reason="append-only trigger is Postgres-only")
@pytest.mark.django_db
def test_ledger_entry_is_append_only_at_db_level(organization, school_factory):
    school = school_factory(organization=organization)
    activate_organization(organization.id)
    entry = LedgerEntry.all_tenants.create(
        organization=organization, school=school, account="cash", debit_minor=100, credit_minor=0,
        currency_code="NGN", ref_type="payment", ref_id=1,
    )

    with pytest.raises(ProgrammingError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE finance_ledger_entry SET debit_minor = %s WHERE id = %s", [999, entry.id]
                )

    with pytest.raises(ProgrammingError, match="append-only"):
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM finance_ledger_entry WHERE id = %s", [entry.id])
