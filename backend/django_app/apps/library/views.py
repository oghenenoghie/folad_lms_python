"""Thin views, fat services (§11 ARCHITECTURE.md). Loan/Fine are create +
read-only plus dedicated transition endpoints (return/mark-lost, pay/waive)
— same shape as apps.examinations' Result, since "what changed and when"
matters more here than free-form editing.
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import require_permission
from apps.core.generics import (
    TenantListCreateAPIView,
    TenantRetrieveAPIView,
    TenantRetrieveUpdateDestroyAPIView,
)
from apps.core.responses import envelope, error_envelope

from .models import LibraryBook, LibraryCopy, LibraryFine, LibraryLoan, LibraryMember
from .serializers import (
    LibraryBookSerializer,
    LibraryCopySerializer,
    LibraryFineSerializer,
    LibraryLoanSerializer,
    LibraryMemberSerializer,
)
from .services import book_service, copy_service, fine_service, loan_service, member_service
from .services.exceptions import LibraryError


class LibraryBookListCreateView(TenantListCreateAPIView):
    serializer_class = LibraryBookSerializer

    def get_queryset(self):
        qs = LibraryBook.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "library_books.create" if self.request.method == "POST" else "library_books.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = book_service.create_book(school=school, actor=self.request.user, **data)


class LibraryBookDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = LibraryBookSerializer

    def get_queryset(self):
        return LibraryBook.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "library_books.view", "PATCH": "library_books.update", "DELETE": "library_books.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        book_service.update_book(book=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        book_service.delete_book(book=instance, actor=self.request.user)


class LibraryCopyListCreateView(TenantListCreateAPIView):
    serializer_class = LibraryCopySerializer

    def get_queryset(self):
        qs = LibraryCopy.objects.filter(deleted_at__isnull=True)
        book_id = self.request.query_params.get("book_id")
        if book_id:
            qs = qs.filter(book__public_id=book_id)
        return qs

    def get_permissions(self):
        code = "library_copies.create" if self.request.method == "POST" else "library_copies.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        book = data.pop("book")
        serializer.instance = copy_service.create_copy(book=book, actor=self.request.user, **data)


class LibraryCopyDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = LibraryCopySerializer

    def get_queryset(self):
        return LibraryCopy.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "library_copies.view", "PATCH": "library_copies.update", "DELETE": "library_copies.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("book", None)
        copy_service.update_copy(copy=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        copy_service.delete_copy(copy=instance, actor=self.request.user)


class LibraryMemberListCreateView(TenantListCreateAPIView):
    serializer_class = LibraryMemberSerializer

    def get_queryset(self):
        qs = LibraryMember.objects.filter(deleted_at__isnull=True)
        school_id = self.request.query_params.get("school_id")
        if school_id:
            qs = qs.filter(school__public_id=school_id)
        return qs

    def get_permissions(self):
        code = "library_members.create" if self.request.method == "POST" else "library_members.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        school = data.pop("school")
        serializer.instance = member_service.create_member(school=school, actor=self.request.user, **data)


class LibraryMemberDetailView(TenantRetrieveUpdateDestroyAPIView):
    serializer_class = LibraryMemberSerializer

    def get_queryset(self):
        return LibraryMember.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        code = {
            "GET": "library_members.view",
            "PATCH": "library_members.update",
            "DELETE": "library_members.delete",
        }[self.request.method]
        return [IsAuthenticated(), require_permission(code)()]

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        data.pop("school", None)
        member_service.update_member(member=serializer.instance, actor=self.request.user, **data)

    def perform_destroy(self, instance):
        member_service.delete_member(member=instance, actor=self.request.user)


class LibraryLoanListCreateView(TenantListCreateAPIView):
    serializer_class = LibraryLoanSerializer

    def get_queryset(self):
        qs = LibraryLoan.objects.filter(deleted_at__isnull=True)
        member_id = self.request.query_params.get("member_id")
        copy_id = self.request.query_params.get("copy_id")
        if member_id:
            qs = qs.filter(member__public_id=member_id)
        if copy_id:
            qs = qs.filter(copy__public_id=copy_id)
        return qs

    def get_permissions(self):
        code = "library_loans.create" if self.request.method == "POST" else "library_loans.view"
        return [IsAuthenticated(), require_permission(code)()]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except LibraryError as exc:
            return error_envelope(str(exc), status=409)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        copy = data.pop("copy")
        member = data.pop("member")
        serializer.instance = loan_service.borrow_book(
            copy=copy, member=member, actor=self.request.user, **data
        )


class LibraryLoanDetailView(TenantRetrieveAPIView):
    serializer_class = LibraryLoanSerializer

    def get_queryset(self):
        return LibraryLoan.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("library_loans.view")()]


class LibraryLoanReturnView(APIView):
    permission_classes = [IsAuthenticated, require_permission("library_loans.update")]

    def post(self, request, public_id):
        try:
            loan = LibraryLoan.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except LibraryLoan.DoesNotExist:
            return error_envelope("loan not found", status=404)
        try:
            loan = loan_service.return_book(loan=loan, actor=request.user)
        except LibraryError as exc:
            return error_envelope(str(exc), status=409)
        return envelope(LibraryLoanSerializer(loan).data, message="book returned")


class LibraryLoanMarkLostView(APIView):
    permission_classes = [IsAuthenticated, require_permission("library_loans.update")]

    def post(self, request, public_id):
        try:
            loan = LibraryLoan.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except LibraryLoan.DoesNotExist:
            return error_envelope("loan not found", status=404)
        try:
            loan = loan_service.mark_lost(loan=loan, actor=request.user)
        except LibraryError as exc:
            return error_envelope(str(exc), status=409)
        return envelope(LibraryLoanSerializer(loan).data, message="loan marked lost")


class LibraryFineListCreateView(TenantListCreateAPIView):
    serializer_class = LibraryFineSerializer

    def get_queryset(self):
        qs = LibraryFine.objects.filter(deleted_at__isnull=True)
        loan_id = self.request.query_params.get("loan_id")
        if loan_id:
            qs = qs.filter(loan__public_id=loan_id)
        return qs

    def get_permissions(self):
        code = "library_fines.create" if self.request.method == "POST" else "library_fines.view"
        return [IsAuthenticated(), require_permission(code)()]

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        loan = data.pop("loan")
        serializer.instance = fine_service.create_fine(loan=loan, actor=self.request.user, **data)


class LibraryFineDetailView(TenantRetrieveAPIView):
    serializer_class = LibraryFineSerializer

    def get_queryset(self):
        return LibraryFine.objects.filter(deleted_at__isnull=True)

    def get_permissions(self):
        return [IsAuthenticated(), require_permission("library_fines.view")()]


class LibraryFinePayView(APIView):
    permission_classes = [IsAuthenticated, require_permission("library_fines.update")]

    def post(self, request, public_id):
        try:
            fine = LibraryFine.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except LibraryFine.DoesNotExist:
            return error_envelope("fine not found", status=404)
        try:
            fine = fine_service.pay_fine(fine=fine, actor=request.user)
        except LibraryError as exc:
            return error_envelope(str(exc), status=409)
        return envelope(LibraryFineSerializer(fine).data, message="fine paid")


class LibraryFineWaiveView(APIView):
    permission_classes = [IsAuthenticated, require_permission("library_fines.update")]

    def post(self, request, public_id):
        try:
            fine = LibraryFine.objects.filter(deleted_at__isnull=True).get(public_id=public_id)
        except LibraryFine.DoesNotExist:
            return error_envelope("fine not found", status=404)
        try:
            fine = fine_service.waive_fine(fine=fine, actor=request.user)
        except LibraryError as exc:
            return error_envelope(str(exc), status=409)
        return envelope(LibraryFineSerializer(fine).data, message="fine waived")
