from unfold.forms import UserChangeForm as UnfoldUserChangeForm
from unfold.forms import UserCreationForm as UnfoldUserCreationForm

from .models import User


class UserCreationForm(UnfoldUserCreationForm):
    class Meta(UnfoldUserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name", "organization")


class UserChangeForm(UnfoldUserChangeForm):
    class Meta(UnfoldUserChangeForm.Meta):
        model = User
        fields = "__all__"
