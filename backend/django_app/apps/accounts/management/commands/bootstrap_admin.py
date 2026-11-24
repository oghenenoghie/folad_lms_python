"""Create the first login on a fresh database: an Organization plus a
superuser attached to it.

`createsuperuser` alone isn't enough: it creates a user with
organization=None, and no roles are seeded (only permissions), so a fresh
install has no account that can use the tenant-scoped API, the `/app/` UI
or the Next.js frontend. Superusers bypass RBAC
(apps.accounts.permissions.HasPermission), so an org-attached superuser is
all a new install needs.

    python manage.py bootstrap_admin --email admin@example.com

The password comes from --password, else $DJANGO_SUPERUSER_PASSWORD (the
same variable `createsuperuser --noinput` reads), else an interactive
prompt. It must pass AUTH_PASSWORD_VALIDATORS.
"""
import getpass
import os
import sys

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.tenancy.context import activate_organization
from apps.tenancy.models import Organization

PASSWORD_ENV_VAR = "DJANGO_SUPERUSER_PASSWORD"


class Command(BaseCommand):
    help = "Create an Organization and a superuser attached to it, for the first login on a fresh database."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Login email for the new superuser.")
        parser.add_argument(
            "--password",
            help=f"Omit to read ${PASSWORD_ENV_VAR}, or to be prompted (keeps it out of shell history).",
        )
        parser.add_argument(
            "--org-name",
            default="Demo School",
            help="Organization to attach the user to; reused if one with this exact name already exists.",
        )
        parser.add_argument("--first-name", default="Admin")
        parser.add_argument("--last-name", default="User")
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Never prompt for a password; fail if none is given.",
        )

    def handle(self, *args, **options):
        email = User.objects.normalize_email(options["email"].strip())
        org_name = options["org_name"].strip()
        if not email:
            raise CommandError("--email must not be empty.")
        if not org_name:
            raise CommandError("--org-name must not be empty.")
        if User.all_tenants.filter(email__iexact=email).exists():
            raise CommandError(f"A user with email {email} already exists; nothing was changed.")

        password = self._resolve_password(options)
        candidate = User(email=email, first_name=options["first_name"], last_name=options["last_name"])
        try:
            validate_password(password, user=candidate)
        except ValidationError as exc:
            raise CommandError("Password rejected: " + " ".join(exc.messages)) from exc

        try:
            with transaction.atomic():
                organization = Organization.objects.filter(name=org_name).order_by("pk").first()
                org_created = organization is None
                if org_created:
                    organization = Organization.objects.create(name=org_name)
                activate_organization(organization.id)
                User.objects.create_superuser(
                    email=email,
                    password=password,
                    first_name=options["first_name"],
                    last_name=options["last_name"],
                    organization=organization,
                )
        finally:
            # Don't leave this connection's RLS context pointing at the org.
            activate_organization(None)

        org_verb = "Created" if org_created else "Using existing"
        self.stdout.write(f"{org_verb} organization '{organization.name}' (id={organization.id}).")
        self.stdout.write(self.style.SUCCESS(f"Created superuser {email} in '{organization.name}'."))
        self.stdout.write("Log in with POST /api/v1/auth/login, the /app/ UI, or the Next.js frontend.")

    def _resolve_password(self, options) -> str:
        if options["password"]:
            return options["password"]
        from_env = os.environ.get(PASSWORD_ENV_VAR)
        if from_env:
            return from_env
        if not (options["interactive"] and sys.stdin.isatty()):
            raise CommandError(f"No password given: pass --password or set ${PASSWORD_ENV_VAR}.")
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Password (again): "):
            raise CommandError("Passwords didn't match.")
        if not password:
            raise CommandError("Password must not be empty.")
        return password
