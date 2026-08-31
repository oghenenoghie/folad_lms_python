"""Thin views, fat services (§11 ARCHITECTURE.md)."""
import secrets
import string

from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User
from apps.schools.models import School
from apps.students.models import Student

_PASSWORD_ALPHABET = string.ascii_letters + string.digits
_PASSWORD_LENGTH = 12


def _generate_password() -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH))


def _generate_placeholder_email(*, student: Student) -> str:
    """A student's own `email` is optional, but `User.email` (the login
    identifier) is required and globally unique. When no real email was
    given, synthesize a stable, unique, non-deliverable one instead — it's
    a login handle, not an inbox, so "forgot password" won't work for it;
    an admin who wants that should fill in `email` on the student.
    """
    base = slugify(f"{student.admission_number}-{student.school.code}-org{student.organization_id}")
    candidate = f"{base}@students.local"
    suffix = 1
    while User.all_tenants.filter(email=candidate).exists():
        candidate = f"{base}-{suffix}@students.local"
        suffix += 1
    return candidate


def provision_login(*, student: Student) -> str:
    """Creates and links the platform login for a student who doesn't
    already have one, with a freshly generated random password. Returns
    the plaintext password — the only moment it's ever available in the
    clear; nothing here stores or logs it.
    """
    email = (student.email or "").strip().lower() or _generate_placeholder_email(student=student)
    password = _generate_password()
    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=student.first_name,
        last_name=student.last_name,
        organization=student.organization,
    )
    student.user = user
    student.save(update_fields=["user"])
    return password


def create_student(*, school: School, actor, **fields) -> Student:
    student = Student.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )
    if student.user_id is None:
        student._generated_password = provision_login(student=student)
    return student


def update_student(*, student: Student, actor, **fields) -> Student:
    for field, value in fields.items():
        setattr(student, field, value)
    student.updated_by = actor
    student.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return student


def delete_student(*, student: Student, actor) -> None:
    student.deleted_at = timezone.now()
    student.updated_by = actor
    student.save(update_fields=["deleted_at", "updated_by", "updated_at"])
