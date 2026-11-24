from django.apps import AppConfig


class TenancyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenancy"
    label = "tenancy"

    def ready(self):
        from django.db.backends.signals import connection_created

        def _reset_rls_guc_on_new_connection(sender, connection, **kwargs):
            # Fires once per physical connection (not per request) — the safe
            # baseline every fresh connection starts from. See middleware.py.
            if connection.vendor != "postgresql":
                return
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_org', '0', false), "
                    "set_config('app.platform_mode', 'false', false)"
                )

        connection_created.connect(_reset_rls_guc_on_new_connection, dispatch_uid="tenancy_reset_rls_guc")
