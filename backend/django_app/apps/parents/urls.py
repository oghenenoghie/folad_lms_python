from django.urls import path

from .views import GuardianDetailView, GuardianListCreateView

urlpatterns = [
    path("guardians", GuardianListCreateView.as_view(), name="guardian-list-create"),
    path("guardians/<uuid:public_id>", GuardianDetailView.as_view(), name="guardian-detail"),
]
