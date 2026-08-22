"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.db import transaction
from django.utils import timezone

from apps.schools.models import AcademicYear, Term


def create_term(*, academic_year: AcademicYear, actor, **fields) -> Term:
    return Term.objects.create(
        organization=academic_year.organization,
        academic_year=academic_year,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_term(*, term: Term, actor, **fields) -> Term:
    for field, value in fields.items():
        setattr(term, field, value)
    term.updated_by = actor
    term.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return term


def delete_term(*, term: Term, actor) -> None:
    term.deleted_at = timezone.now()
    term.updated_by = actor
    term.save(update_fields=["deleted_at", "updated_by", "updated_at"])


def activate_term(*, term: Term, actor) -> Term:
    """Marks `term` as the academic year's current one, atomically unsetting
    whichever term previously held that flag."""
    with transaction.atomic():
        list(
            Term.objects.select_for_update()
            .filter(academic_year_id=term.academic_year_id, is_current=True)
            .exclude(pk=term.pk)
        )
        Term.objects.filter(academic_year_id=term.academic_year_id, is_current=True).exclude(
            pk=term.pk
        ).update(is_current=False, updated_by=actor, updated_at=timezone.now())
        term.is_current = True
        term.updated_by = actor
        term.save(update_fields=["is_current", "updated_by", "updated_at"])
    return term
