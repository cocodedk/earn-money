"""Header redaction for stub 1.2 server-headers.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/02-server-headers.md
"""
from __future__ import annotations


SENSITIVE_HEADERS: frozenset[str] = frozenset({
    "set-cookie",
    "cookie",
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "x-auth-token",
})

REDACTED_VALUE = "[redacted]"


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        name: (REDACTED_VALUE if name.lower() in SENSITIVE_HEADERS else value)
        for name, value in headers.items()
    }
