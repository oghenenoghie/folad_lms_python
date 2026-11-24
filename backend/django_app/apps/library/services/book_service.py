"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.library.models import LibraryBook
from apps.schools.models import School


def create_book(*, school: School, actor, **fields) -> LibraryBook:
    return LibraryBook.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_book(*, book: LibraryBook, actor, **fields) -> LibraryBook:
    for field, value in fields.items():
        setattr(book, field, value)
    book.updated_by = actor
    book.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return book


def delete_book(*, book: LibraryBook, actor) -> None:
    book.deleted_at = timezone.now()
    book.updated_by = actor
    book.save(update_fields=["deleted_at", "updated_by", "updated_at"])
