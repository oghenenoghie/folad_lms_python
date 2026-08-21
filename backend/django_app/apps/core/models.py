"""Abstract base models shared across domain apps (see §5 ARCHITECTURE.md
key-shape convention: bigint PK + uuid public_id + standard audit columns).
"""
import uuid

from django.conf import settings
from django.db import models


class UUIDPublicIdModel(models.Model):
    """A `bigint` identity PK plus a `uuid public_id` — the only identifier
    ever exposed externally."""

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        abstract = True


class BaseModel(UUIDPublicIdModel, TimestampedModel):
    class Meta:
        abstract = True
