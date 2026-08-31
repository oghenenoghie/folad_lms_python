from django import forms
from django.utils.safestring import mark_safe

from apps.core.storage import InvalidUpload, get_presigned_download_url, save_document, validate_upload

from .models import Student


class StudentAdminForm(forms.ModelForm):
    """`photo_storage_key` (see models.py) is a storage key, not a real
    Django FileField, so it can't get Django's native upload widget for
    free — this surfaces a normal file input instead, uploads through
    apps.core.storage in StudentAdmin.save_model, and stores the resulting
    key. `remove_photo` clears an existing one without requiring a new
    upload.
    """

    photo = forms.ImageField(
        required=False, help_text="JPEG or PNG, up to 10MB. Leave blank to keep the current photo."
    )
    remove_photo = forms.BooleanField(required=False, help_text="Remove the current photo.")

    class Meta:
        model = Student
        exclude = ["photo_storage_key"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.photo_storage_key:
            # The URL is a freshly computed, non-user-controlled presigned
            # link (or local storage path) — safe to render as-is.
            url = get_presigned_download_url(self.instance.photo_storage_key)
            self.fields["photo"].help_text = mark_safe(
                f'Current photo: <a href="{url}" target="_blank" rel="noopener">view</a>. '
                "Upload a new file to replace it, or leave blank to keep it."
            )

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo is None:
            return photo
        content = photo.read()
        try:
            validate_upload(content=content, content_type=photo.content_type)
        except InvalidUpload as exc:
            raise forms.ValidationError(str(exc)) from exc
        photo.seek(0)
        return photo


def save_student_photo(*, student: Student, form: StudentAdminForm) -> None:
    """Applies `form`'s `photo`/`remove_photo` fields to an already-saved
    `student` — called from StudentAdmin.save_model after the base
    save(), since the upload itself doesn't touch any other model field.
    """
    photo = form.cleaned_data.get("photo")
    remove_photo = form.cleaned_data.get("remove_photo")
    if photo is not None:
        key = save_document(
            key_prefix=f"student-photos/{student.organization_id}",
            filename=photo.name,
            content=photo.read(),
            content_type=photo.content_type,
        )
        student.photo_storage_key = key
        student.save(update_fields=["photo_storage_key"])
    elif remove_photo and student.photo_storage_key:
        student.photo_storage_key = ""
        student.save(update_fields=["photo_storage_key"])
