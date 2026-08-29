"""Thin views, fat services (§11 ARCHITECTURE.md). No RBAC permission beyond
IsAuthenticated — the summary is always the requesting user's own role-
appropriate view, never another user's or the whole organization's raw
data, same self-scoping rationale as apps.communication's Notification/
Message endpoints.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.responses import envelope

from .services import dashboard_service


class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return envelope(dashboard_service.get_summary(user=request.user))
