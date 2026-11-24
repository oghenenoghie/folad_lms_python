from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import connections
from django.db.utils import OperationalError
from django.http import Http404
from django.views.generic import TemplateView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness probe: the process is up. No dependency checks."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"success": True, "data": {"status": "ok"}, "message": "healthy", "errors": []})


class ReadyView(APIView):
    """Readiness probe: the process can serve traffic (DB + cache reachable)."""

    permission_classes = [AllowAny]

    def get(self, request):
        checks = {"database": self._check_database(), "cache": self._check_cache()}
        ready = all(checks.values())
        payload = {"success": ready, "data": {"status": "ready" if ready else "not_ready", "checks": checks},
                   "message": "ready" if ready else "not ready", "errors": [] if ready else ["dependency check failed"]}
        return Response(payload, status=200 if ready else 503)

    @staticmethod
    def _check_database() -> bool:
        try:
            connections["default"].cursor()
            return True
        except OperationalError:
            return False

    @staticmethod
    def _check_cache() -> bool:
        try:
            cache.set("readiness-probe", "1", timeout=5)
            return cache.get("readiness-probe") == "1"
        except Exception:
            return False


class DesignSystemView(TemplateView):
    """Kitchen-sink demo of every Phase 2 design-system component, so the
    component library can be verified visually in a browser rather than by
    code review alone. Dev-only — 404s unless DEBUG is on (see urls.py).
    """

    template_name = "design_system.html"

    def dispatch(self, request, *args, **kwargs):
        if not settings.DEBUG:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["breadcrumb_items"] = [("Home", "/"), ("Design system", None)]
        context["sample_page"] = Paginator(range(1, 58), 10).page(3)
        return context
