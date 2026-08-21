from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache_keys import invalidate_user_permissions
from .models import RolePermission, UserRole


@receiver([post_save, post_delete], sender=UserRole)
def _invalidate_on_user_role_change(sender, instance: UserRole, **kwargs):
    invalidate_user_permissions(instance.user_id, instance.user.organization_id)


@receiver([post_save, post_delete], sender=RolePermission)
def _invalidate_on_role_permission_change(sender, instance: RolePermission, **kwargs):
    affected = UserRole.objects.filter(role_id=instance.role_id).select_related("user")
    for user_role in affected:
        invalidate_user_permissions(user_role.user_id, user_role.user.organization_id)
