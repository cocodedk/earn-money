"""Secret/PII redactor for stub 1.19 sql_orm_errors.

Spec §Safety + §PII handling: error excerpts must be scrubbed of
tokens, keys, credentials, connection strings, and PII before they
land in `Finding.data.snippet_redacted`.

Re-uses stub 1.17's redaction pattern table verbatim — the same six
patterns (jwt / bearer / api_key / email / url_creds / secret) cover
both stubs' needs. Lifting that table to `_shared/secrets.py` is a
tracked follow-up per the Phase 1 closeout plan; this thin wrapper
exists so the eventual lift is a one-line import change here.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

from apps.stubs.verbose_api_errors.redaction import redact as _redact_text


def redact(text: str) -> str:
    """Redact secrets / PII from a snippet before persistence.

    Idempotent: ``redact(redact(x)) == redact(x)``.
    """
    return _redact_text(text)
