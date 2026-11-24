from django.urls import path

from .views import (
    DashboardSummaryView,
    MyAssignmentsView,
    MyAttendanceView,
    MyChildrenView,
    MyInvoicesView,
    MyResultsView,
)

urlpatterns = [
    path("dashboard/summary", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("dashboard/my-children", MyChildrenView.as_view(), name="dashboard-my-children"),
    path("dashboard/my-assignments", MyAssignmentsView.as_view(), name="dashboard-my-assignments"),
    path("dashboard/my-attendance", MyAttendanceView.as_view(), name="dashboard-my-attendance"),
    path("dashboard/my-results", MyResultsView.as_view(), name="dashboard-my-results"),
    path("dashboard/my-invoices", MyInvoicesView.as_view(), name="dashboard-my-invoices"),
]
