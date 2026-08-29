from django.db import migrations

CODES = [
    ("library_books.view", "library_books", "view", "View library books"),
    ("library_books.create", "library_books", "create", "Add library books"),
    ("library_books.update", "library_books", "update", "Update library books"),
    ("library_books.delete", "library_books", "delete", "Delete library books"),
    ("library_copies.view", "library_copies", "view", "View library copies"),
    ("library_copies.create", "library_copies", "create", "Add library copies"),
    ("library_copies.update", "library_copies", "update", "Update library copies"),
    ("library_copies.delete", "library_copies", "delete", "Delete library copies"),
    ("library_members.view", "library_members", "view", "View library members"),
    ("library_members.create", "library_members", "create", "Enroll library members"),
    ("library_members.update", "library_members", "update", "Update library members"),
    ("library_members.delete", "library_members", "delete", "Remove library members"),
    ("library_loans.view", "library_loans", "view", "View library loans"),
    ("library_loans.create", "library_loans", "create", "Borrow books"),
    ("library_loans.update", "library_loans", "update", "Return or mark loans lost"),
    ("library_fines.view", "library_fines", "view", "View library fines"),
    ("library_fines.create", "library_fines", "create", "Issue library fines"),
    ("library_fines.update", "library_fines", "update", "Pay or waive library fines"),
]


def forwards(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    for code, module, action, description in CODES:
        Permission.objects.get_or_create(
            code=code, defaults={"module": module, "action": action, "description": description}
        )


def backwards(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Permission.objects.filter(code__in=[code for code, *_ in CODES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
