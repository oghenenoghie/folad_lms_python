"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.finance.models import FeeStructure
from apps.schools.models import Term


def create_fee_structure(*, term: Term, actor, **fields) -> FeeStructure:
    return FeeStructure.objects.create(
        organization=term.organization,
        school=term.academic_year.school,
        academic_year=term.academic_year,
        term=term,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_fee_structure(*, fee_structure: FeeStructure, actor, **fields) -> FeeStructure:
    for field, value in fields.items():
        setattr(fee_structure, field, value)
    fee_structure.updated_by = actor
    fee_structure.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return fee_structure


def delete_fee_structure(*, fee_structure: FeeStructure, actor) -> None:
    fee_structure.deleted_at = timezone.now()
    fee_structure.updated_by = actor
    fee_structure.save(update_fields=["deleted_at", "updated_by", "updated_at"])
