from django import forms
from unfold.forms import UserChangeForm as UnfoldUserChangeForm
from unfold.forms import UserCreationForm as UnfoldUserCreationForm
from unfold.widgets import UnfoldAdminSelect2MultipleWidget

from .models import Permission, Role, User


class UserCreationForm(UnfoldUserCreationForm):
    class Meta(UnfoldUserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name", "organization")


class UserChangeForm(UnfoldUserChangeForm):
    class Meta(UnfoldUserChangeForm.Meta):
        model = User
        fields = "__all__"


class RoleAdminForm(forms.ModelForm):
    """Role.permissions is a ManyToManyField(through=RolePermission), which
    Django Admin never lets a ModelForm edit directly (it silently drops
    `through` M2M fields from the auto-generated form). RolePermission has
    no fields beyond the two FKs it joins, so `role.permissions.set(...)`
    is safe to call directly (see Django's M2M-through docs) — this field
    just surfaces that as a normal multi-select, saved in RoleAdmin.save_model.
    """

    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.order_by("module", "action"),
        required=False,
        widget=UnfoldAdminSelect2MultipleWidget,
    )

    class Meta:
        model = Role
        fields = ["name", "label", "is_system", "organization"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["permissions"].initial = self.instance.permissions.all()
