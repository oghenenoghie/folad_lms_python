from django.contrib import admin, messages
from django.db import IntegrityError, transaction
from unfold.admin import ModelAdmin

from apps.core.admin import TenantAdminMixin

from .models import Student
from .services.student_service import provision_login


@admin.register(Student)
class StudentAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["admission_number", "first_name", "last_name", "school", "enrollment_status"]
    search_fields = ["admission_number", "first_name", "last_name"]
    list_filter = ["enrollment_status", "school"]
    autocomplete_fields = ["organization", "school", "user"]

    def save_model(self, request, obj, form, change):
        # Admin saves go straight through the form/model, never through
        # student_service.create_student() — this is the Admin-side
        # equivalent of the auto-provisioning that API creation gets there.
        creating = not change
        super().save_model(request, obj, form, change)
        if not creating or obj.user_id is not None:
            return

        try:
            # Admin's own changeform_view wraps this whole save in one
            # atomic() block that continues on to log_addition() afterward
            # — without this inner savepoint, catching the IntegrityError
            # here would still leave that outer transaction poisoned (see
            # the identical note in core/generics.py's EnvelopeCreateMixin).
            with transaction.atomic():
                password = provision_login(student=obj)
        except IntegrityError:
            self.message_user(
                request,
                f"Student saved, but a login could not be created: '{obj.email}' is already in use "
                "by another account. Fix the email and save again, or link an existing user manually.",
                level=messages.ERROR,
            )
        else:
            self.message_user(
                request,
                f"Login created for {obj}: email={obj.user.email}, password={password} "
                "— shown once, save it now.",
                level=messages.SUCCESS,
            )
