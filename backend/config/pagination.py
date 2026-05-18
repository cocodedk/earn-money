"""DRF pagination class — agreed with frontend agent in API contract.

Response shape: `{count, next, previous, results}`.
Query params: `?page=N&page_size=N` (default 50, capped at 200).
"""
from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
