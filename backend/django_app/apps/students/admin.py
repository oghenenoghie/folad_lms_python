from django.contrib import admin, messages
from django.db import IntegrityError, transaction
from unfold.admin import ModelAdmin, TabularInline

from apps.academics.models import Enrollment
from apps.core.admin import TenantAdminMixin, TenantFKAdminMixin
from apps.parents.models import GuardianStudent

from .forms import StudentAdminForm, save_student_photo
from .models import Achievement, Student
from .services.student_service import provision_login


class EnrollmentInline(TenantFKAdminMixin, TabularInline):
    model = Enrollment
    fk_name = "student"
    extra = 1
    fields = ["class_arm", "academic_year", "status", "effective_from", "effective_to"]
    autocomplete_fields = ["class_arm", "academic_year"]


class GuardianStudentInline(TenantFKAdminMixin, TabularInline):
    model = GuardianStudent
    fk_name = "student"
    extra = 1
    fields = ["guardian", "relationship_type", "is_primary"]
    autocomplete_fields = ["guardian"]


@admin.register(Student)
class StudentAdmin(TenantAdminMixin, ModelAdmin):
    form = StudentAdminForm
    inlines = [EnrollmentInline, GuardianStudentInline]
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
        save_student_photo(student=obj, form=form)
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

    def save_formset(self, request, form, formset, change):
        # Enrollment/GuardianStudent both require `organization`, which the
        # inline form never exposes (it's always derived from the parent
        # Student, never picked by hand) — backfill it, plus the usual
        # audit fields, before Django's own formset.save() does the
        # actual create/update/delete.
        for inline_form in formset.forms:
            if inline_form.instance.pk is None:
                inline_form.instance.organization = form.instance.organization
                inline_form.instance.created_by = request.user
            inline_form.instance.updated_by = request.user
        formset.save()


@admin.register(Achievement)
class AchievementAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["title", "student", "category", "school", "awarded_on"]
    search_fields = ["title", "student__first_name", "student__last_name"]
    list_filter = ["category", "school"]
    autocomplete_fields = ["organization", "school", "student"]
