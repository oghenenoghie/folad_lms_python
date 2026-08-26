from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("parents", "0006_platform_mode_rls"),
    ]

    operations = [
        migrations.RenameField(
            model_name="guardianstudent",
            old_name="is_primary_contact",
            new_name="is_primary",
        ),
    ]
