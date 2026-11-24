"""Custom authentication backend for Django's session-based auth (used by
the admin login form, in particular — the REST API uses its own
JWTAuthentication in apps/accounts/authentication.py instead).

apps.accounts.models.User.objects is tenant-scoped by default
(apps.tenancy.managers.TenantManager), and there is no tenant context yet
during session authentication — you need to already know who's logging in
to know their organization, not the other way around.
ModelBackend.authenticate() resolves correctly via
UserManager.get_by_natural_key()'s override in apps/accounts/managers.py,
but ModelBackend.get_user() (called on every subsequent request to reload
`request.user` from the session) queries `_default_manager.get(pk=...)`
directly and would otherwise always return nothing, logging every admin
user straight back out after a successful login. Override just that.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

UserModel = get_user_model()


class TenantAwareModelBackend(ModelBackend):
    def get_user(self, user_id):
        try:
            user = UserModel.all_tenants.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None
