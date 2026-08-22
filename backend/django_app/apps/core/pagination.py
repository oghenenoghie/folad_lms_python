from rest_framework.pagination import PageNumberPagination


class EnvelopePageNumberPagination(PageNumberPagination):
    """Paginates into the {results, pagination} shape expected inside the
    envelope's `data` key (§9 ARCHITECTURE.md), not DRF's default
    {count, next, previous, results} response."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_data(self, results: list) -> dict:
        return {
            "results": results,
            "pagination": {
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "total_pages": self.page.paginator.num_pages,
                "total_count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
            },
        }
