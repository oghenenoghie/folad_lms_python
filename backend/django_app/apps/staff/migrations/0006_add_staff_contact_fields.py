from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("staff", "0005_platform_mode_rls"),
    ]

    operations = [
        migrations.AddField(
            model_name="staff",
            name="phone",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="staff",
            name="email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
    ]
