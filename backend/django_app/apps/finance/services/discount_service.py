"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.finance.models import Discount
from apps.schools.models import School


def create_discount(*, school: School, actor, **fields) -> Discount:
    return Discount.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_discount(*, discount: Discount, actor, **fields) -> Discount:
    for field, value in fields.items():
        setattr(discount, field, value)
    discount.updated_by = actor
    discount.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return discount


def delete_discount(*, discount: Discount, actor) -> None:
    discount.deleted_at = timezone.now()
    discount.updated_by = actor
    discount.save(update_fields=["deleted_at", "updated_by", "updated_at"])


def compute_discount_amount_minor(*, discount: Discount | None, base_amount_minor: int) -> int:
    """Best-effort: returns 0 when no discount applies, rather than raising —
    a line is allowed to carry no discount at all."""
    if discount is None:
        return 0
    if discount.discount_type == "percentage":
        return int(base_amount_minor * discount.percentage / 100)
    return min(discount.fixed_amount_minor, base_amount_minor)
