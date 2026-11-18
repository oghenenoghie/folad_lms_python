import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models

from apps.tenancy.db import add_platform_mode_bypass, enable_rls


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0016_platform_mode_rls"),
        ("academics", "0005_alter_subject_code"),
        ("accounts", "0005_role_public_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="CBTImportJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("source_name", models.CharField(max_length=255)),
                ("source_format", models.CharField(
                    choices=[("csv", "CSV"), ("xlsx", "Excel workbook"), ("docx", "Word document"), ("pdf", "PDF document")],
                    max_length=10,
                )),
                ("storage_key", models.CharField(max_length=500)),
                ("source_sha256", models.CharField(max_length=64)),
                ("source_size_bytes", models.PositiveBigIntegerField()),
                ("idempotency_key", models.CharField(max_length=128)),
                ("parser_version", models.CharField(default="v1", max_length=40)),
                ("status", models.CharField(
                    choices=[
                        ("uploaded", "Uploaded"), ("queued", "Queued"), ("extracting", "Extracting"),
                        ("needs_mapping", "Needs Mapping"), ("validating", "Validating"),
                        ("ready_to_commit", "Ready to Commit"), ("committing", "Committing"),
                        ("completed", "Completed"), ("completed_with_errors", "Completed with Errors"),
                        ("failed", "Failed"), ("cancelled", "Cancelled"),
                    ],
                    default="uploaded",
                    max_length=24,
                )),
                ("mapping", models.JSONField(blank=True, default=dict)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("failure_code", models.CharField(blank=True, default="", max_length=64)),
                ("failure_message", models.TextField(blank=True, default="")),
                ("created_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="tenancy.organization",
                )),
                ("subject", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="cbt_import_jobs",
                    to="academics.subject",
                )),
                ("class_level", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="cbt_import_jobs",
                    to="academics.classlevel",
                )),
                ("updated_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "cbt_import_job",
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("organization", "idempotency_key"),
                        name="uq_cbt_import_org_idem",
                    ),
                ],
                "indexes": [
                    models.Index(
                        fields=["organization", "status", "created_at"],
                        name="cbt_imp_job_status_idx",
                    ),
                    models.Index(
                        fields=["organization", "source_sha256"],
                        name="cbt_imp_job_hash_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="CBTImportItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("sequence", models.PositiveIntegerField()),
                ("source_locator", models.JSONField(blank=True, default=dict)),
                ("source_fingerprint", models.CharField(max_length=64)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("validation_status", models.CharField(
                    choices=[
                        ("pending", "Pending"), ("valid", "Valid"),
                        ("invalid", "Invalid"), ("warning", "Warning"),
                    ],
                    default="pending",
                    max_length=10,
                )),
                ("created_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("job", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="items",
                    to="cbt.cbtimportjob",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="tenancy.organization",
                )),
                ("committed_question", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="cbt_import_items",
                    to="cbt.question",
                )),
                ("updated_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "cbt_import_item",
                "ordering": ["job", "sequence"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("job", "sequence"),
                        name="uq_cbt_imp_item_sequence",
                    ),
                    models.UniqueConstraint(
                        fields=("job", "source_fingerprint"),
                        name="uq_cbt_imp_item_fingerprint",
                    ),
                ],
                "indexes": [
                    models.Index(
                        fields=["organization", "job", "validation_status"],
                        name="cbt_imp_item_status_idx",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="CBTImportIssue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("severity", models.CharField(
                    choices=[("error", "Error"), ("warning", "Warning"), ("info", "Information")],
                    max_length=10,
                )),
                ("code", models.CharField(max_length=80)),
                ("message", models.TextField()),
                ("source_locator", models.JSONField(blank=True, default=dict)),
                ("created_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("item", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="issues",
                    to="cbt.cbtimportitem",
                )),
                ("job", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="issues",
                    to="cbt.cbtimportjob",
                )),
                ("organization", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="+",
                    to="tenancy.organization",
                )),
                ("updated_by", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "cbt_import_issue",
                "ordering": ["created_at", "id"],
                "indexes": [
                    models.Index(
                        fields=["organization", "job", "created_at"],
                        name="cbt_imp_issue_job_idx",
                    ),
                ],
            },
        ),
        enable_rls("cbt_import_job"),
        add_platform_mode_bypass("cbt_import_job"),
        enable_rls("cbt_import_item"),
        add_platform_mode_bypass("cbt_import_item"),
        enable_rls("cbt_import_issue"),
        add_platform_mode_bypass("cbt_import_issue"),
    ]
