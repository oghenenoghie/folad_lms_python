"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.db import transaction
from django.utils import timezone

from apps.library.models import LibraryFine, LibraryLoan
from apps.library.services.exceptions import InvalidLoanState


def create_fine(*, loan: LibraryLoan, actor, **fields) -> LibraryFine:
    fields.setdefault("currency_code", loan.organization.currency_code)
    return LibraryFine.objects.create(
        organization=loan.organization, loan=loan, created_by=actor, updated_by=actor, **fields
    )


def pay_fine(*, fine: LibraryFine, actor) -> LibraryFine:
    with transaction.atomic():
        fine = LibraryFine.objects.select_for_update().get(pk=fine.pk)
        if fine.status != "pending":
            raise InvalidLoanState(f"cannot pay a fine that is already '{fine.status}'")
        fine.status = "paid"
        fine.paid_at = timezone.now()
        fine.updated_by = actor
        fine.save(update_fields=["status", "paid_at", "updated_by", "updated_at"])
    return fine


def waive_fine(*, fine: LibraryFine, actor) -> LibraryFine:
    with transaction.atomic():
        fine = LibraryFine.objects.select_for_update().get(pk=fine.pk)
        if fine.status != "pending":
            raise InvalidLoanState(f"cannot waive a fine that is already '{fine.status}'")
        fine.status = "waived"
        fine.updated_by = actor
        fine.save(update_fields=["status", "updated_by", "updated_at"])
    return fine
