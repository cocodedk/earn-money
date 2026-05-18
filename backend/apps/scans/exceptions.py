"""Exception for invalid scan-run state transitions.

Inherits from DRF's `APIException` so it auto-converts to a 400 response
with `{"detail": "..."}`. The frontend's `parseApiError` handles this
shape as a non-field error (banner above the form).
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import APIException


class InvalidTransition(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Invalid scan-run state transition."
    default_code = "invalid_transition"
