from django.urls import path

from .views import (
    HostelAllocationDetailView,
    HostelAllocationListCreateView,
    HostelAllocationVacateView,
    HostelBedDetailView,
    HostelBedListCreateView,
    HostelBuildingDetailView,
    HostelBuildingListCreateView,
    HostelDetailView,
    HostelIncidentDetailView,
    HostelIncidentListCreateView,
    HostelIncidentResolveView,
    HostelListCreateView,
    HostelRoomDetailView,
    HostelRoomListCreateView,
)

urlpatterns = [
    path("hostels", HostelListCreateView.as_view(), name="hostel-list-create"),
    path("hostels/<uuid:public_id>", HostelDetailView.as_view(), name="hostel-detail"),
    path("hostel-buildings", HostelBuildingListCreateView.as_view(), name="hostel-building-list-create"),
    path(
        "hostel-buildings/<uuid:public_id>",
        HostelBuildingDetailView.as_view(),
        name="hostel-building-detail",
    ),
    path("hostel-rooms", HostelRoomListCreateView.as_view(), name="hostel-room-list-create"),
    path("hostel-rooms/<uuid:public_id>", HostelRoomDetailView.as_view(), name="hostel-room-detail"),
    path("hostel-beds", HostelBedListCreateView.as_view(), name="hostel-bed-list-create"),
    path("hostel-beds/<uuid:public_id>", HostelBedDetailView.as_view(), name="hostel-bed-detail"),
    path(
        "hostel-allocations", HostelAllocationListCreateView.as_view(), name="hostel-allocation-list-create"
    ),
    path(
        "hostel-allocations/<uuid:public_id>",
        HostelAllocationDetailView.as_view(),
        name="hostel-allocation-detail",
    ),
    path(
        "hostel-allocations/<uuid:public_id>/vacate",
        HostelAllocationVacateView.as_view(),
        name="hostel-allocation-vacate",
    ),
    path("hostel-incidents", HostelIncidentListCreateView.as_view(), name="hostel-incident-list-create"),
    path(
        "hostel-incidents/<uuid:public_id>",
        HostelIncidentDetailView.as_view(),
        name="hostel-incident-detail",
    ),
    path(
        "hostel-incidents/<uuid:public_id>/resolve",
        HostelIncidentResolveView.as_view(),
        name="hostel-incident-resolve",
    ),
]
