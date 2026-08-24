from django.contrib import admin
from django.urls import include, path

from apps.core.views import HealthView

urlpatterns = [
    path("admin/", admin.site.urls),
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
]
