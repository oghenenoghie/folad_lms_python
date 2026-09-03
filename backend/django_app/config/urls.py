from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.core.views import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Bare domain root has no content of its own — the server-rendered UI
    # lives under /app/ (see below), which itself redirects to /app/login
    # for a signed-out visitor via LoginRequiredMixin.
    path("", RedirectView.as_view(pattern_name="web:home", permanent=False)),
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
