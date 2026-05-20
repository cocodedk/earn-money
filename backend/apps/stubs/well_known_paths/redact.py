"""Per-family redaction for stub `well_known_paths`.

Each family's response excerpt is scrubbed of secrets / PII / binary
content before persistence per spec §Safety + §PII handling. The six
strategies share an `apps.stubs.verbose_api_errors.redaction.redact`
call for the generic secret/PII pattern table (jwt / bearer / api_key
/ email / url_creds / secret), layered on top of family-specific
rules:

* env  — values redacted to `<KEY>=<REDACTED>`; keys preserved.
* git  — binary pack/object bytes → `<binary-redacted bytes=N>`; ASCII
         refs/HEAD/config preserved with generic secret redaction.
* config_files — JSON/YAML/INI text, generic secret redaction only.
* logs — generic secret redaction (catches IPs?email/JWT/keys).
* backup_archives — magic-byte prefix preserved, body redacted whole.
* db_dumps — `CREATE TABLE` verbatim; `INSERT INTO ... VALUES (...)`
             value-tuples redacted to `(<REDACTED>)`. SQLite binary
             → same archive treatment.

Spec sources: 1.20-1.25 §Safety + §PII handling.
"""
from __future__ import annotations

import re

from apps.stubs.verbose_api_errors.redaction import redact as _generic_redact

from ._types import Family


_ENV_LINE_RE = re.compile(
    r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*.*$", flags=re.MULTILINE,
)
_INSERT_VALUES_RE = re.compile(
    r"(INSERT INTO\s+[\"`\w.]+\s*(?:\([^)]*\))?\s*VALUES\s*)(\([^)]*\))",
    flags=re.IGNORECASE | re.DOTALL,
)
# Binary heuristic — non-printable byte ratio over a small prefix.
_PRINTABLE_RATIO_THRESHOLD = 0.85
_PREFIX_BYTES = 256


def _is_binary(body: bytes) -> bool:
    """Coarse binary check: ≥15% of first 256 bytes are non-printable."""
    if not body:
        return False
    prefix = body[:_PREFIX_BYTES]
    printable = sum(1 for b in prefix if 0x20 <= b < 0x7F or b in (0x09, 0x0A, 0x0D))
    return (printable / len(prefix)) < _PRINTABLE_RATIO_THRESHOLD


def _redact_binary(body: bytes, *, preserve_prefix: int) -> str:
    """Magic-byte prefix (hex) preserved at the front; body redacted."""
    prefix_hex = body[:preserve_prefix].hex(" ")
    return f"<magic:{prefix_hex}> <binary-redacted bytes={len(body)}>"


def _redact_env(text: str) -> str:
    """Preserve keys, redact values."""
    redacted = _ENV_LINE_RE.sub(r"\1=<REDACTED>", text)
    return _generic_redact(redacted)


def _redact_db_dump(text: str) -> str:
    """Keep CREATE TABLE verbatim; redact INSERT INTO ... VALUES tuples."""
    return _generic_redact(_INSERT_VALUES_RE.sub(r"\1(<REDACTED>)", text))


def redact(*, family: Family, body: bytes) -> str:
    """Return the redacted snippet for persistence.

    Caller already truncated `body` to the per-family byte cap.
    """
    if family == "backup_archives":
        return _redact_binary(body, preserve_prefix=4)
    if family == "db_dumps" and _is_binary(body):
        return _redact_binary(body, preserve_prefix=16)
    if family == "git" and _is_binary(body):
        return _redact_binary(body, preserve_prefix=4)

    text = body.decode("utf-8", errors="replace")
    if family == "env":
        return _redact_env(text)
    if family == "db_dumps":
        return _redact_db_dump(text)
    # config_files / logs / ascii-git → generic secret+PII sweep.
    return _generic_redact(text)
