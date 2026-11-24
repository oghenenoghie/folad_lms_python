from django.urls import path

from .views import (
    PeriodDetailView,
    PeriodListCreateView,
    RoomDetailView,
    RoomListCreateView,
    TimetableSlotDetailView,
    TimetableSlotListCreateView,
)

urlpatterns = [
    path("rooms", RoomListCreateView.as_view(), name="room-list-create"),
    path("rooms/<uuid:public_id>", RoomDetailView.as_view(), name="room-detail"),
    path("periods", PeriodListCreateView.as_view(), name="period-list-create"),
    path("periods/<uuid:public_id>", PeriodDetailView.as_view(), name="period-detail"),
    path("timetable-slots", TimetableSlotListCreateView.as_view(), name="timetable-slot-list-create"),
    path(
        "timetable-slots/<uuid:public_id>",
        TimetableSlotDetailView.as_view(),
        name="timetable-slot-detail",
    ),
]
