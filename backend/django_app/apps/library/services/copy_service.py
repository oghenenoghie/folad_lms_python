"""Thin views, fat services (§11 ARCHITECTURE.md). No client-facing update to
`status` here — that only ever changes as a side effect of borrowing/
returning a copy (see loan_service)."""
from django.utils import timezone

from apps.library.models import LibraryBook, LibraryCopy


def create_copy(*, book: LibraryBook, actor, **fields) -> LibraryCopy:
    return LibraryCopy.objects.create(
        organization=book.organization, book=book, created_by=actor, updated_by=actor, **fields
    )


def update_copy(*, copy: LibraryCopy, actor, **fields) -> LibraryCopy:
    for field, value in fields.items():
        setattr(copy, field, value)
    copy.updated_by = actor
    copy.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return copy


def delete_copy(*, copy: LibraryCopy, actor) -> None:
    copy.deleted_at = timezone.now()
    copy.updated_by = actor
    copy.save(update_fields=["deleted_at", "updated_by", "updated_at"])
