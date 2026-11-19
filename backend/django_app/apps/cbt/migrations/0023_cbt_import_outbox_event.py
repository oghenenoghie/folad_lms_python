import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from apps.tenancy.db import add_platform_mode_bypass, enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0022_join_duplicate_merge_leaves"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tenancy", "__latest__"),
    ]

    operations = [
        migrations.CreateModel(
            name="CBTImportOutboxEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("event_type", models.CharField(max_length=80)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("publishing", "Publishing"), ("published", "Published"), ("failed", "Failed")], default="pending", max_length=20)),
                ("attempts", models.PositiveIntegerField(default=0)),
                ("available_at", models.DateTimeField()),
                ("locked_at", models.DateTimeField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, default="", max_length=500)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="outbox_events", to="cbt.cbtimportjob")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
            ],
            options={"db_table": "cbt_import_outbox_event", "ordering": ["available_at", "created_at"]},
        ),
        migrations.AddConstraint(
            model_name="cbtimportoutboxevent",
            constraint=models.UniqueConstraint(fields=("job", "event_type"), name="uq_cbt_import_outbox_job_event"),
        ),
        migrations.AddIndex(
            model_name="cbtimportoutboxevent",
            index=models.Index(fields=["organization", "status", "available_at"], name="cbt_outbox_org_status_idx"),
        ),
        enable_rls("cbt_import_outbox_event"),
        add_platform_mode_bypass("cbt_import_outbox_event"),
    ]
