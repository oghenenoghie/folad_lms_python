from django.db import migrations

CODES = [
    ("report_card_weightings.view", "report_card_weightings", "view", "View report card weightings"),
    (
        "report_card_weightings.create",
        "report_card_weightings",
        "create",
        "Create report card weightings",
    ),
    (
        "report_card_weightings.update",
        "report_card_weightings",
        "update",
        "Update report card weightings",
    ),
    ("report_cards.view", "report_cards", "view", "View report cards"),
    ("report_cards.generate", "report_cards", "generate", "Generate/regenerate report cards"),
    ("report_cards.update", "report_cards", "update", "Edit report card comments"),
    ("report_cards.publish", "report_cards", "publish", "Publish/unpublish report cards"),
]


# apps.examinations' old bare PDF-job ReportCard (removed in
# examinations.0010) used "report_cards.create" for its one client
# action, "request a report card". The new engine's equivalent action is
# admin-only generation, seeded above as "report_cards.generate" — this
# code is retired along with it rather than left orphaned.
RETIRED_CODES = ["report_cards.create"]


def forwards(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code, module, action, description in CODES:
        Permission.objects.get_or_create(
            code=code, defaults={"module": module, "action": action, "description": description}
        )
    Permission.objects.filter(code__in=RETIRED_CODES).delete()


def backwards(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code__in=[code for code, *_ in CODES]).delete()
    Permission.objects.get_or_create(
        code="report_cards.create",
        defaults={
            "module": "report_cards",
            "action": "create",
            "description": "Request report card generation",
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("report_cards", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
