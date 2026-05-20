"""Signature library for stub 1.4 backend-hints.

Split by source axis to stay under the 200-line cap. The public
surface — `SIGNATURES`, `CATEGORIES`, `MATCH_SOURCES` — is re-exported
here so importers keep `from .signatures import ...` working.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/04-backend-hints.md
"""
from __future__ import annotations

from .bodies import BODY_SIGNATURES
from .cookies import COOKIE_SIGNATURES
from .headers import HEADER_SIGNATURES


CATEGORIES: set[str] = {
    "app_framework",
    "app_runtime",
    "session_marker",
    "error_page",
    "unknown",
}

MATCH_SOURCES: set[str] = {
    "header",
    "cookie",
    "body",
}


SIGNATURES: list[dict] = (
    COOKIE_SIGNATURES + HEADER_SIGNATURES + BODY_SIGNATURES
)

__all__ = ("CATEGORIES", "MATCH_SOURCES", "SIGNATURES")
