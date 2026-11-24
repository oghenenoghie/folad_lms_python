"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.transport.models import RouteStop, TransportRoute


def create_route_stop(*, route: TransportRoute, actor, **fields) -> RouteStop:
    return RouteStop.objects.create(
        organization=route.organization, route=route, created_by=actor, updated_by=actor, **fields
    )


def update_route_stop(*, route_stop: RouteStop, actor, **fields) -> RouteStop:
    for field, value in fields.items():
        setattr(route_stop, field, value)
    route_stop.updated_by = actor
    route_stop.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return route_stop


def delete_route_stop(*, route_stop: RouteStop, actor) -> None:
    route_stop.deleted_at = timezone.now()
    route_stop.updated_by = actor
    route_stop.save(update_fields=["deleted_at", "updated_by", "updated_at"])
