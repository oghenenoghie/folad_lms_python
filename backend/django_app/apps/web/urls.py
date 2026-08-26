from django.urls import include, path

from .views.auth import WebLoginView, WebLogoutView
from .views.dashboard import HomeView
from .views.security import MFAEnrollStartView, MFAVerifySubmitView, SecurityView

app_name = "web"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("login", WebLoginView.as_view(), name="login"),
    path("logout", WebLogoutView.as_view(), name="logout"),
    path("account/security", SecurityView.as_view(), name="security"),
    path("account/security/mfa/enroll", MFAEnrollStartView.as_view(), name="mfa-enroll-start"),
    path("account/security/mfa/verify", MFAVerifySubmitView.as_view(), name="mfa-verify-submit"),
    path("schools/", include("apps.web.urls_schools")),
]
