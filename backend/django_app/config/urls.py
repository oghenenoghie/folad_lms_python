from django.contrib import admin
from django.urls import include, path

from apps.core.views import HealthView
from apps.web.views.marketing import LandingView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Public landing page — the server-rendered UI itself lives under
    # /app/ (see below) and is session-gated (LoginRequiredMixin), so a
    # signed-out visitor hitting "/" needs something to actually render
    # rather than bouncing straight to /app/login.
    path("", LandingView.as_view(), name="landing"),
    # Railway healthcheck target (railway.toml). Same liveness probe as
    # /api/v1/health, kept under both paths since the latter is the
    # versioned API surface and the former is the deployment-platform
    # convention this task calls for.
    path("health/", HealthView.as_view(), name="health-root"),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.schools.urls")),
    path("api/v1/", include("apps.students.urls")),
    path("api/v1/", include("apps.staff.urls")),
    path("api/v1/", include("apps.parents.urls")),
    path("api/v1/", include("apps.academics.urls")),
    path("api/v1/", include("apps.attendance.urls")),
    path("api/v1/", include("apps.timetable.urls")),
    path("api/v1/", include("apps.examinations.urls")),
    path("api/v1/", include("apps.report_cards.urls")),
    path("api/v1/", include("apps.finance.urls")),
    path("api/v1/", include("apps.library.urls")),
    path("api/v1/", include("apps.inventory.urls")),
    path("api/v1/", include("apps.transport.urls")),
    path("api/v1/", include("apps.hostel.urls")),
    path("api/v1/", include("apps.assignments.urls")),
    path("api/v1/", include("apps.communication.urls")),
    path("api/v1/", include("apps.documents.urls")),
    path("api/v1/", include("apps.dashboards.urls")),
    path("api/v1/", include("apps.reports.urls")),
    # Server-rendered UI (UI_MIGRATION_PLAN.md) — session-authenticated,
    # entirely separate from the JWT-authenticated api/v1/ surface above.
    path("app/", include("apps.web.urls")),
]
