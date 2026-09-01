import uuid

from django.db import migrations, models


def backfill_public_ids(apps, schema_editor):
    # AddField's SQL-level column default only runs once for all existing
    # rows (it can't invoke a Python callable per row) — a bare AddField
    # with default=uuid.uuid4 would give every already-seeded system role
    # the *same* UUID, breaking uniqueness. Backfilling here, through the
    # ORM, actually calls uuid.uuid4() once per row.
    Role = apps.get_model("accounts", "Role")
    for role in Role.objects.all():
        role.public_id = uuid.uuid4()
        role.save(update_fields=["public_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_platform_mode_rls"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="public_id",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, null=True, unique=False),
        ),
        migrations.RunPython(backfill_public_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="role",
            name="public_id",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
