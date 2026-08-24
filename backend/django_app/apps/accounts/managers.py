from django.contrib.auth.base_user import BaseUserManager

from apps.tenancy.managers import TenantManager


class UserManager(TenantManager, BaseUserManager):
    """Tenant-scoped by default (`objects`), with the create_user/create_superuser
    helpers Django's auth machinery expects on the default manager."""

    use_in_migrations = True

    def get_by_natural_key(self, email: str):
        """Django's ModelBackend (session-based auth — the admin login
        form, in particular) calls this on `_default_manager` to resolve
        the user *before* authentication succeeds, so there is no tenant
        context yet to scope by (TenantManager.get_queryset() would return
        nothing and every login would fail, correct password or not).
        Bypass tenant scoping for this one lookup via `all_tenants` — the
        same escape hatch apps/accounts/authentication.py's JWTAuthentication
        and auth_service.login() already use for the identical reason.
        RBAC and object-level tenant checks still apply everywhere else via
        the scoped `objects` manager.
        """
        return self.model.all_tenants.get(**{self.model.USERNAME_FIELD: email})

    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("User must have an email address")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")
        return self._create_user(email, password, **extra_fields)
