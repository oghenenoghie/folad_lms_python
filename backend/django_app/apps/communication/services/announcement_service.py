"""Thin views, fat services (§11 ARCHITECTURE.md). publish_announcement() is
the concrete case this milestone's "notification center" exit criterion is
built against: it resolves the announcement's audience to actual platform
users and creates one Notification per recipient, in the same transaction
as flipping published_at — a published announcement and its notifications
appear together or not at all.
"""
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.communication.models import Announcement, Notification
from apps.schools.models import School


def create_announcement(*, school: School, actor, **fields) -> Announcement:
    return Announcement.objects.create(
        organization=school.organization, school=school, created_by=actor, updated_by=actor, **fields
    )


def update_announcement(*, announcement: Announcement, actor, **fields) -> Announcement:
    for field, value in fields.items():
        setattr(announcement, field, value)
    announcement.updated_by = actor
    announcement.save(update_fields=[*fields.keys(), "updated_by", "updated_at"])
    return announcement


def delete_announcement(*, announcement: Announcement, actor) -> None:
    announcement.deleted_at = timezone.now()
    announcement.updated_by = actor
    announcement.save(update_fields=["deleted_at", "updated_by", "updated_at"])


def _recipients_for(announcement: Announcement):
    org = announcement.organization
    school = announcement.school
    querysets = []
    if announcement.audience in ("all", "students"):
        querysets.append(User.objects.filter(organization=org, student_profile__school=school))
    if announcement.audience in ("all", "staff"):
        querysets.append(User.objects.filter(organization=org, staff_profile__school=school))
    if announcement.audience in ("all", "parents"):
        querysets.append(User.objects.filter(organization=org, guardian_profile__isnull=False))
    ids: set[int] = set()
    for qs in querysets:
        ids.update(qs.values_list("id", flat=True))
    return User.objects.filter(id__in=ids)


def publish_announcement(*, announcement: Announcement, actor) -> Announcement:
    with transaction.atomic():
        announcement.published_at = timezone.now()
        announcement.updated_by = actor
        announcement.save(update_fields=["published_at", "updated_by", "updated_at"])
        Notification.objects.bulk_create(
            [
                Notification(
                    organization=announcement.organization,
                    recipient=user,
                    notification_type="announcement",
                    title=announcement.title,
                    body=announcement.body,
                    ref_type="announcement",
                    ref_id=announcement.id,
                    created_by=actor,
                    updated_by=actor,
                )
                for user in _recipients_for(announcement)
            ]
        )
    return announcement
