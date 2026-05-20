"""Signature library for stub 1.3 frontend-framework.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/03-frontend-framework.md

Split across category-files to stay under the 200-line cap. The
public surface — `SIGNATURES`, `CATEGORIES`, `MATCH_SOURCES` — is
re-exported here so importers can keep `from .signatures import ...`.
"""
from __future__ import annotations

from .css_frameworks import CSS_FRAMEWORK_SIGNATURES
from .frameworks import FRAMEWORK_SIGNATURES
from .libraries import LIBRARY_SIGNATURES
from .meta_frameworks import META_FRAMEWORK_SIGNATURES


CATEGORIES: set[str] = {
    "framework",
    "meta_framework",
    "library",
    "css_framework",
    "unknown",
}

MATCH_SOURCES: set[str] = {
    "html_body",
    "script_src_path",
    "asset_body",
}


SIGNATURES: list[dict] = (
    FRAMEWORK_SIGNATURES
    + META_FRAMEWORK_SIGNATURES
    + LIBRARY_SIGNATURES
    + CSS_FRAMEWORK_SIGNATURES
)

__all__ = ("CATEGORIES", "MATCH_SOURCES", "SIGNATURES")
