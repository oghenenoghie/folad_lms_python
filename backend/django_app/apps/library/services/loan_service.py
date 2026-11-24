"""Thin views, fat services (§11 ARCHITECTURE.md). borrow_book/return_book/
mark_lost keep LibraryCopy.status and LibraryLoan.status in lock-step inside
one transaction — a copy's status is never edited directly by a client (see
copy_service), only ever as a side effect of one of these three calls.
select_for_update() on the copy row means two concurrent borrow attempts on
the same copy can't both succeed; uq_library_loan_one_open_per_copy (see
models.py) backs that up as a real DB constraint too.
"""
from django.db import transaction
from django.utils import timezone

from apps.library.models import LibraryCopy, LibraryLoan, LibraryMember
from apps.library.services.exceptions import CopyNotAvailable, InvalidLoanState


def borrow_book(*, copy: LibraryCopy, member: LibraryMember, actor, due_date, **fields) -> LibraryLoan:
    with transaction.atomic():
        copy = LibraryCopy.objects.select_for_update().get(pk=copy.pk)
        if copy.status != "available":
            raise CopyNotAvailable(f"copy is '{copy.status}', not available to borrow")
        loan = LibraryLoan.objects.create(
            organization=copy.organization,
            copy=copy,
            member=member,
            borrowed_date=fields.pop("borrowed_date", timezone.now().date()),
            due_date=due_date,
            created_by=actor,
            updated_by=actor,
            **fields,
        )
        copy.status = "loaned"
        copy.updated_by = actor
        copy.save(update_fields=["status", "updated_by", "updated_at"])
    return loan


def return_book(*, loan: LibraryLoan, actor) -> LibraryLoan:
    with transaction.atomic():
        loan = LibraryLoan.objects.select_for_update().get(pk=loan.pk)
        if loan.status not in ("borrowed", "overdue"):
            raise InvalidLoanState(f"cannot return a loan that is already '{loan.status}'")
        loan.status = "returned"
        loan.returned_date = timezone.now().date()
        loan.updated_by = actor
        loan.save(update_fields=["status", "returned_date", "updated_by", "updated_at"])

        copy = LibraryCopy.objects.select_for_update().get(pk=loan.copy_id)
        copy.status = "available"
        copy.updated_by = actor
        copy.save(update_fields=["status", "updated_by", "updated_at"])
    return loan


def mark_lost(*, loan: LibraryLoan, actor) -> LibraryLoan:
    with transaction.atomic():
        loan = LibraryLoan.objects.select_for_update().get(pk=loan.pk)
        if loan.status not in ("borrowed", "overdue"):
            raise InvalidLoanState(f"cannot mark a loan lost once it is '{loan.status}'")
        loan.status = "lost"
        loan.updated_by = actor
        loan.save(update_fields=["status", "updated_by", "updated_at"])

        copy = LibraryCopy.objects.select_for_update().get(pk=loan.copy_id)
        copy.status = "lost"
        copy.updated_by = actor
        copy.save(update_fields=["status", "updated_by", "updated_at"])
    return loan
