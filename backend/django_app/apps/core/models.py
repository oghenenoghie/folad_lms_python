"""Abstract base models shared across domain apps (see §5 ARCHITECTURE.md
key-shape convention: bigint PK + uuid public_id + standard audit columns).
"""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, router


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

    def _perform_unique_checks(self, unique_checks):
        """Model.validate_unique()'s stock implementation queries each
        unique_check via `model_class._default_manager` — for every model
        here that's the tenant-scoped `TenantManager` (`objects`), which
        returns nothing with no organization context active. Django Admin's
        session-based auth never activates one (same gap TenantAdminMixin
        and TenantFKAdminMixin already work around for the changelist and
        FK widgets), so a genuine duplicate silently "validates" as unique
        there and then crashes with a raw IntegrityError once the real,
        unscoped database constraint rejects the insert instead of
        surfacing as a normal form error.

        Only takes over when there's no organization context (the gap this
        exists for) and the model actually has an `all_tenants` manager to
        fall back to; otherwise defers to Django's own implementation
        unchanged, so callers with a genuine organization active (i.e. the
        JWT API, where uniqueness is correctly checked within that org)
        are unaffected.
        """
        from django.core.exceptions import NON_FIELD_ERRORS
        from django.db import connection

        from apps.tenancy.context import get_current_organization_id

        if get_current_organization_id() is not None:
            return super()._perform_unique_checks(unique_checks)

        errors = {}
        for model_class, unique_check in unique_checks:
            manager = getattr(model_class, "all_tenants", None)
            if manager is None:
                errors.update(super()._perform_unique_checks([(model_class, unique_check)]))
                continue

            lookup_kwargs = {}
            for field_name in unique_check:
                f = self._meta.get_field(field_name)
                lookup_value = getattr(self, f.attname)
                if lookup_value is None or (
                    lookup_value == "" and connection.features.interprets_empty_strings_as_nulls
                ):
                    continue
                if f in model_class._meta.pk_fields and not self._state.adding:
                    continue
                lookup_kwargs[str(field_name)] = lookup_value

            if len(unique_check) != len(lookup_kwargs):
                continue

            qs = manager.filter(**lookup_kwargs)
            model_class_pk = self._get_pk_val(model_class._meta)
            if not self._state.adding and self._is_pk_set(model_class._meta):
                qs = qs.exclude(pk=model_class_pk)
            if qs.exists():
                key = unique_check[0] if len(unique_check) == 1 else NON_FIELD_ERRORS
                errors.setdefault(key, []).append(self.unique_error_message(model_class, unique_check))
        return errors

    def validate_constraints(self, exclude=None):
        """`Meta.constraints`-based `UniqueConstraint`s are a *separate*
        Django validation path from `_perform_unique_checks` above (which
        only ever covers `unique_together`/field-level `unique=True`) —
        `ModelForm._post_clean()` reaches this one via
        `full_clean(validate_unique=False)`, which still runs
        `validate_constraints()` unconditionally. `UniqueConstraint.validate()`
        has the exact same gap: it queries via `model._default_manager`
        (`TenantManager`), which is empty with no organization context
        active, so a genuine duplicate silently passes validation in
        Django Admin and only surfaces as a raw IntegrityError once the
        real, unscoped database constraint rejects the insert.

        `UniqueConstraint.validate()` takes the model class as a plain
        argument rather than resolving it from `self`, so there's no clean
        per-call hook to swap the manager it uses. `Model._default_manager`
        is a read-only property computed from the model's `_meta`, backed
        by `Options.default_manager` — a `cached_property`, whose computed
        value lives in `model_class._meta.__dict__` once first accessed.
        Overwriting that cache entry (not the read-only property itself)
        temporarily repoints `_default_manager` at `all_tenants` only
        around this call, then always restores the original (`finally`) —
        and only when there's no organization context and the model has an
        `all_tenants` manager; otherwise this defers to Django's own
        implementation unchanged.
        """
        from apps.tenancy.context import get_current_organization_id

        if get_current_organization_id() is not None:
            return super().validate_constraints(exclude=exclude)

        using = router.db_for_write(self.__class__, instance=self)
        errors = {}
        for model_class, model_constraints in self.get_constraints():
            all_tenants = getattr(model_class, "all_tenants", None)
            for constraint in model_constraints:
                swapped = all_tenants is not None
                if swapped:
                    original_manager = model_class._default_manager  # forces caching
                    model_class._meta.__dict__["default_manager"] = all_tenants
                try:
                    constraint.validate(model_class, self, exclude=exclude, using=using)
                except ValidationError as e:
                    if getattr(e, "code", None) == "unique" and len(constraint.fields) == 1:
                        errors.setdefault(constraint.fields[0], []).append(e)
                    else:
                        errors = e.update_error_dict(errors)
                finally:
                    if swapped:
                        model_class._meta.__dict__["default_manager"] = original_manager
        if errors:
            raise ValidationError(errors)
