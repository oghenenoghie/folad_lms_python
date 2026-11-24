from django.urls import path

from .views import (
    RouteStopDetailView,
    RouteStopListCreateView,
    TransportAssignmentDetailView,
    TransportAssignmentListCreateView,
    TransportRouteDetailView,
    TransportRouteListCreateView,
    VehicleDetailView,
    VehicleListCreateView,
    VehicleMaintenanceDetailView,
    VehicleMaintenanceListCreateView,
)

urlpatterns = [
    path("vehicles", VehicleListCreateView.as_view(), name="vehicle-list-create"),
    path("vehicles/<uuid:public_id>", VehicleDetailView.as_view(), name="vehicle-detail"),
    path("transport-routes", TransportRouteListCreateView.as_view(), name="transport-route-list-create"),
    path(
        "transport-routes/<uuid:public_id>",
        TransportRouteDetailView.as_view(),
        name="transport-route-detail",
    ),
    path("route-stops", RouteStopListCreateView.as_view(), name="route-stop-list-create"),
    path("route-stops/<uuid:public_id>", RouteStopDetailView.as_view(), name="route-stop-detail"),
    path(
        "transport-assignments",
        TransportAssignmentListCreateView.as_view(),
        name="transport-assignment-list-create",
    ),
    path(
        "transport-assignments/<uuid:public_id>",
        TransportAssignmentDetailView.as_view(),
        name="transport-assignment-detail",
    ),
    path(
        "vehicle-maintenance",
        VehicleMaintenanceListCreateView.as_view(),
        name="vehicle-maintenance-list-create",
    ),
    path(
        "vehicle-maintenance/<uuid:public_id>",
        VehicleMaintenanceDetailView.as_view(),
        name="vehicle-maintenance-detail",
    ),
]
