from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("students", "0004_platform_mode_rls"),
    ]

    operations = [
        migrations.AddField(
            model_name="student",
            name="gender",
            field=models.CharField(
                blank=True,
                default="",
                max_length=10,
                choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
            ),
        ),
    ]
