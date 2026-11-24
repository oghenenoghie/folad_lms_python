from django.urls import path

from .views import (
    LibraryBookDetailView,
    LibraryBookListCreateView,
    LibraryCopyDetailView,
    LibraryCopyListCreateView,
    LibraryFineDetailView,
    LibraryFineListCreateView,
    LibraryFinePayView,
    LibraryFineWaiveView,
    LibraryLoanDetailView,
    LibraryLoanListCreateView,
    LibraryLoanMarkLostView,
    LibraryLoanReturnView,
    LibraryMemberDetailView,
    LibraryMemberListCreateView,
)

urlpatterns = [
    path("library-books", LibraryBookListCreateView.as_view(), name="library-book-list-create"),
    path("library-books/<uuid:public_id>", LibraryBookDetailView.as_view(), name="library-book-detail"),
    path("library-copies", LibraryCopyListCreateView.as_view(), name="library-copy-list-create"),
    path("library-copies/<uuid:public_id>", LibraryCopyDetailView.as_view(), name="library-copy-detail"),
    path("library-members", LibraryMemberListCreateView.as_view(), name="library-member-list-create"),
    path(
        "library-members/<uuid:public_id>", LibraryMemberDetailView.as_view(), name="library-member-detail"
    ),
    path("library-loans", LibraryLoanListCreateView.as_view(), name="library-loan-list-create"),
    path("library-loans/<uuid:public_id>", LibraryLoanDetailView.as_view(), name="library-loan-detail"),
    path(
        "library-loans/<uuid:public_id>/return",
        LibraryLoanReturnView.as_view(),
        name="library-loan-return",
    ),
    path(
        "library-loans/<uuid:public_id>/mark-lost",
        LibraryLoanMarkLostView.as_view(),
        name="library-loan-mark-lost",
    ),
    path("library-fines", LibraryFineListCreateView.as_view(), name="library-fine-list-create"),
    path("library-fines/<uuid:public_id>", LibraryFineDetailView.as_view(), name="library-fine-detail"),
    path(
        "library-fines/<uuid:public_id>/pay", LibraryFinePayView.as_view(), name="library-fine-pay"
    ),
    path(
        "library-fines/<uuid:public_id>/waive", LibraryFineWaiveView.as_view(), name="library-fine-waive"
    ),
]
