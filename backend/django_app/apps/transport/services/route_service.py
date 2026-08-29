"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.schools.models import School
from apps.transport.models import TransportRoute


def create_route(*, school: School, actor, **fields) -> TransportRoute:
    return TransportRoute.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_route(*, route: TransportRoute, actor, **fields) -> TransportRoute:
    for field, value in fields.items():
        setattr(route, field, value)
    route.updated_by = actor
    route.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return route


def delete_route(*, route: TransportRoute, actor) -> None:
    route.deleted_at = timezone.now()
    route.updated_by = actor
    route.save(update_fields=["deleted_at", "updated_by", "updated_at"])
