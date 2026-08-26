from django.db import IntegrityError, transaction
from rest_framework import generics

from .pagination import EnvelopePageNumberPagination
from .responses import envelope, error_envelope


class EnvelopeListMixin:
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            return envelope(self.paginator.get_paginated_data(serializer.data))
        return envelope({"results": serializer.data, "pagination": None})


class EnvelopeCreateMixin:
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Models here use Meta.constraints (models.UniqueConstraint), which —
        # unlike the legacy Meta.unique_together — DRF's ModelSerializer does
        # NOT auto-translate into a pre-save validator. Without this, a
        # uniqueness conflict would surface as a raw, unhandled IntegrityError
        # (500) instead of a clean 409. The inner atomic() is required, not
        # cosmetic: catching IntegrityError without first isolating the write
        # in its own savepoint leaves the *surrounding* transaction (pytest's
        # per-test transaction, or any future caller-level atomic() block)
        # poisoned for every query after this one, even though the exception
        # itself was caught.
        try:
            with transaction.atomic():
                self.perform_create(serializer)
        except IntegrityError:
            return error_envelope("a record with these values already exists", status=409)
        return envelope(serializer.data, message="created successfully", status=201)


class EnvelopeRetrieveMixin:
    def retrieve(self, request, *args, **kwargs):
        return envelope(self.get_serializer(self.get_object()).data)


class EnvelopeUpdateMixin:
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        # See the atomic() note in EnvelopeCreateMixin.create() above.
        try:
            with transaction.atomic():
                self.perform_update(serializer)
        except IntegrityError:
            return error_envelope("a record with these values already exists", status=409)
        return envelope(serializer.data, message="updated successfully")


class EnvelopeDestroyMixin:
    def destroy(self, request, *args, **kwargs):
        self.perform_destroy(self.get_object())
        return envelope(message="deleted successfully")


class TenantListCreateAPIView(EnvelopeListMixin, EnvelopeCreateMixin, generics.GenericAPIView):
    pagination_class = EnvelopePageNumberPagination

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class TenantRetrieveUpdateDestroyAPIView(
    EnvelopeRetrieveMixin, EnvelopeUpdateMixin, EnvelopeDestroyMixin, generics.GenericAPIView
):
    lookup_field = "public_id"
    lookup_url_kwarg = "public_id"

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)
