from django.urls import path

from .views import LoginView, LogoutView, MeView, MFAEnrollView, MFAVerifyView, RefreshView

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/refresh", RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("auth/mfa/enroll", MFAEnrollView.as_view(), name="auth-mfa-enroll"),
    path("auth/mfa/verify", MFAVerifyView.as_view(), name="auth-mfa-verify"),
    path("auth/me", MeView.as_view(), name="auth-me"),
]
