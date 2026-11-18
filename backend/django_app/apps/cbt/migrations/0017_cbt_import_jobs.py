# Generated for durable CBT import jobs.
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("cbt", "0016_platform_mode_rls"),
        ("academics", "0005_alter_subject_code"),
        ("schools", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
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
                ("source_format", models.CharField(choices=[("csv", "CSV"), ("xlsx", "Excel workbook"), ("docx", "Word document"), ("pdf", "PDF document")], max_length=10)),
                ("storage_key", models.CharField(max_length=500)),
                ("source_sha256", models.CharField(max_length=64)),
                ("source_size_bytes", models.PositiveBigIntegerField()),
                ("idempotency_key", models.CharField(max_length=128)),
                ("parser_version", models.CharField(default="spreadsheet-v1", max_length=40)),
                ("status", models.CharField(choices=[("uploaded", "Uploaded"), ("queued", "Queued"), ("extracting", "Extracting"), ("needs_mapping", "Needs Mapping"), ("validating", "Validating"), ("ready_to_commit", "Ready to Commit"), ("committing", "Committing"), ("completed", "Completed"), ("completed_with_errors", "Completed with Errors"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="uploaded", max_length=30)),
                ("mapping", models.JSONField(blank=True, default=dict)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("failure_code", models.CharField(blank=True, default="", max_length=80)),
                ("failure_message", models.TextField(blank=True, default="")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cbt_import_jobs", to=settings.AUTH_USER_MODEL)),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cbt_import_jobs", to="schools.school")),
                ("subject", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cbt_import_jobs", to="academics.subject")),
                ("class_level", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cbt_import_jobs", to="academics.classlevel")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "cbt_import_job", "ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="cbtimportjob",
            constraint=models.UniqueConstraint(fields=("organization", "idempotency_key"), name="uq_cbt_import_job_org_idem"),
        ),
        migrations.AddIndex(
            model_name="cbtimportjob",
            index=models.Index(fields=["organization", "status", "created_at"], name="cbt_impjob_org_status_idx"),
        ),
        migrations.AddIndex(
            model_name="cbtimportjob",
            index=models.Index(fields=["organization", "source_sha256"], name="cbt_impjob_org_hash_idx"),
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
                ("payload", models.JSONField(default=dict)),
                ("validation_status", models.CharField(choices=[("pending", "Pending"), ("valid", "Valid"), ("invalid", "Invalid"), ("warning", "Warning")], default="pending", max_length=20)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="cbt.cbtimportjob")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("committed_question", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="imported_items", to="cbt.question")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "cbt_import_item", "ordering": ["job", "sequence"]},
        ),
        migrations.AddConstraint(
            model_name="cbtimportitem",
            constraint=models.UniqueConstraint(fields=("job", "sequence"), name="uq_cbt_import_item_job_seq"),
        ),
        migrations.AddConstraint(
            model_name="cbtimportitem",
            constraint=models.UniqueConstraint(fields=("job", "source_fingerprint"), name="uq_cbt_import_item_fingerprint"),
        ),
        migrations.AddIndex(
            model_name="cbtimportitem",
            index=models.Index(fields=["organization", "job", "validation_status"], name="cbt_impitem_org_job_val_idx"),
        ),
        migrations.CreateModel(
            name="CBTImportIssue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("severity", models.CharField(choices=[("error", "Error"), ("warning", "Warning"), ("info", "Information")], max_length=10)),
                ("code", models.CharField(max_length=80)),
                ("message", models.TextField()),
                ("source_locator", models.JSONField(blank=True, default=dict)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="issues", to="cbt.cbtimportjob")),
                ("item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="issues", to="cbt.cbtimportitem")),
                ("organization", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="tenancy.organization")),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "cbt_import_issue", "ordering": ["created_at"]},
        ),
        migrations.AddIndex(
            model_name="cbtimportissue",
            index=models.Index(fields=["organization", "job", "severity"], name="cbt_impissue_org_job_sev_idx"),
        ),
    ]
