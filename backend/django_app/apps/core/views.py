from django.core.cache import cache
from django.db import connections
from django.db.utils import OperationalError
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
