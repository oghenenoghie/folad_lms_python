import pytest

from apps.accounts.models import Permission, Role, RolePermission, UserRole
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


@pytest.mark.django_db
def test_borrow_return_lifecycle(
    api_client, organization, user_factory, school_factory, student_factory,
    library_book_factory, library_copy_factory, library_member_factory,
):
    school = school_factory(organization=organization)
    student = student_factory(school=school)
    book = library_book_factory(school=school)
    copy = library_copy_factory(book=book)
    member = library_member_factory(school=school, student=student)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "library_loans.view", "library_loans.create", "library_loans.update", "library_copies.view")
    _login(api_client, "a@example.com", "s3cret-pass!")

    borrow = api_client.post(
        "/api/v1/library-loans",
        {"copy": str(copy.public_id), "member": str(member.public_id), "due_date": "2025-09-15"},
        format="json",
    )
    assert borrow.status_code == 201
    loan_public_id = borrow.json()["data"]["public_id"]

    copy.refresh_from_db()
    assert copy.status == "loaned"

    second_borrow = api_client.post(
        "/api/v1/library-loans",
        {"copy": str(copy.public_id), "member": str(member.public_id), "due_date": "2025-09-15"},
        format="json",
    )
    assert second_borrow.status_code == 409

    returned = api_client.post(f"/api/v1/library-loans/{loan_public_id}/return")
    assert returned.status_code == 200
    assert returned.json()["data"]["status"] == "returned"

    copy.refresh_from_db()
    assert copy.status == "available"

    # Now that the copy is free again, a fresh loan on it should succeed.
    third_borrow = api_client.post(
        "/api/v1/library-loans",
        {"copy": str(copy.public_id), "member": str(member.public_id), "due_date": "2025-10-01"},
        format="json",
    )
    assert third_borrow.status_code == 201


@pytest.mark.django_db
def test_fine_pay_and_waive(
    api_client, organization, user_factory, school_factory, student_factory,
    library_book_factory, library_copy_factory, library_member_factory, library_loan_factory,
):
    school = school_factory(organization=organization)
    student = student_factory(school=school)
    book = library_book_factory(school=school)
    copy = library_copy_factory(book=book)
    member = library_member_factory(school=school, student=student)
    loan = library_loan_factory(copy=copy, member=member)

    user = user_factory(organization=organization, email="a@example.com", password="s3cret-pass!")
    _grant(user, "library_fines.view", "library_fines.create", "library_fines.update")
    _login(api_client, "a@example.com", "s3cret-pass!")

    created = api_client.post(
        "/api/v1/library-fines",
        {"loan": str(loan.public_id), "amount_minor": 500, "reason": "Late return"},
        format="json",
    )
    assert created.status_code == 201
    fine_public_id = created.json()["data"]["public_id"]

    paid = api_client.post(f"/api/v1/library-fines/{fine_public_id}/pay")
    assert paid.status_code == 200
    assert paid.json()["data"]["status"] == "paid"

    already_paid = api_client.post(f"/api/v1/library-fines/{fine_public_id}/waive")
    assert already_paid.status_code == 409


@pytest.mark.django_db
def test_library_app_layer_tenant_isolation(
    organization, other_organization, school_factory, library_book_factory,
):
    library_book_factory(school=school_factory(organization=organization))
    library_book_factory(school=school_factory(organization=other_organization))

    activate_organization(organization.id)
    from apps.library.models import LibraryBook

    visible = LibraryBook.objects.all()
    assert visible.count() == 1
    assert visible.first().organization_id == organization.id
