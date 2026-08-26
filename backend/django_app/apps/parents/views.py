"""Thin views, fat services (§11 ARCHITECTURE.md)."""
from apps.accounts.permissions import require_permission
from apps.core.generics import TenantListCreateAPIView, TenantRetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated

from .models import Guardian
from .serializers import GuardianSerializer
from .services import guardian_service


class GuardianListCreateView(TenantListCreateAPIView):
    serializer_class = GuardianSerializer

    def get_queryset(self):
        return Guardian.objects.filter(deleted_at__isnull=True).order_by("last_name", "first_name")

    def get_permissions(self):
        code = "guardians.create" if self.request.method == "POST" else "guardians.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        serializer.instance = guardian_service.create_guardian(
            actor=self.request.user, **serializer.validated_data
        )


class GuardianDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = GuardianSerializer

    def get_queryset(self):
        return Guardian.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {"GET": "guardians.view", "PATCH": "guardians.update", "DELETE": "guardians.delete"}[
            self.request.method
        ]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        guardian_service.update_guardian(
            guardian=serializer.instance, actor=self.request.user, **serializer.validated_data
        )

    def perform_destroy(self, instance):
        guardian_service.delete_guardian(guardian=instance, actor=self.request.user)
