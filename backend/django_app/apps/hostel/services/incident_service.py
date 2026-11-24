"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from django.utils import timezone

from apps.hostel.models import Hostel, HostelIncident


def report_incident(*, hostel: Hostel, actor, **fields) -> HostelIncident:
    return HostelIncident.objects.create(
        organization=hostel.organization,
        hostel=hostel,
        reported_by=actor,
        created_by=actor,
        updated_by=actor,
        **fields,
    )


def update_incident(*, incident: HostelIncident, actor, **fields) -> HostelIncident:
    for field, value in fields.items():
        setattr(incident, field, value)
    incident.updated_by = actor
    incident.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return incident


def resolve_incident(*, incident: HostelIncident, actor) -> HostelIncident:
    incident.status = "resolved"
    incident.resolved_at = timezone.now()
    incident.updated_by = actor
    incident.save(update_fields=["status", "resolved_at", "updated_by", "updated_at"])
    return incident


def delete_incident(*, incident: HostelIncident, actor) -> None:
    incident.deleted_at = timezone.now()
    incident.updated_by = actor
    incident.save(update_fields=["deleted_at", "updated_by", "updated_at"])
