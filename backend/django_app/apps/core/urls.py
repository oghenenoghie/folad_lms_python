from django.urls import path

from .views import DesignSystemView, HealthView, ReadyView

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("ready", ReadyView.as_view(), name="ready"),
    # Dev-only component-library preview (404s outside DEBUG) — deliberately
    # under api/v1/ alongside the rest of apps.core's urls.py rather than a
    # new top-level path, since it's a debugging aid, not a product surface.
    path("_design-system", DesignSystemView.as_view(), name="design-system"),
]
