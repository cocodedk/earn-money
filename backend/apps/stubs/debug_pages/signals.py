"""Pure-function signal detectors for stub 1.10.

Three signal families per spec §Detection logic:
- `match_framework_signature(body, content_type)`: returns the
  strongest matching framework signature, or None. A match means
  ALL of the signature's body markers are present and (if specified)
  the content type matches. Always emits confidence=high — these
  signatures are tuned to be specific enough that any match is
  authoritative.
- `find_stack_trace_markers(body)`: returns spec leaked_data_classes
  labels for stack-trace and absolute-path leakage.
- `find_env_leak_markers(body)`: returns spec leaked_data_classes
  labels for environment-variable and secret-like-value leakage.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/10-debug-pages.md
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .signatures import FRAMEWORK_SIGNATURES, DebugPageKind, Signature


@dataclass(frozen=True)
class SignatureMatch:
    kind: DebugPageKind
    # Kept as `str` (not Literal) because the downstream
    # `Finding.confidence` column is a free-form CharField — a shared
    # cookbook-wide Confidence Literal is tracked as a follow-up.
    confidence: str
    markers_matched: tuple[str, ...]


def match_framework_signature(
    body: str, content_type: str = "",
) -> SignatureMatch | None:
    """Return the first framework signature whose markers ALL appear
    in `body` (case-insensitive). Returns None when nothing matches.

    Spec §Confidence rules: a known framework marker yields confidence
    high — these signatures are chosen to be specific enough that
    any match is authoritative."""
    if not body:
        return None
    lowered = body.lower()
    lowered_ct = (content_type or "").lower()
    for sig in FRAMEWORK_SIGNATURES:
        if not _content_type_allowed(sig, lowered_ct):
            continue
        if all(marker in lowered for marker in sig.body_markers):
            return SignatureMatch(
                kind=sig.kind,
                confidence="high",
                markers_matched=sig.body_markers,
            )
    return None


def _content_type_allowed(sig: Signature, lowered_ct: str) -> bool:
    if not sig.content_type_includes:
        return True
    return any(ct in lowered_ct for ct in sig.content_type_includes)


# Stack-trace prose markers: framework-agnostic phrases that only
# appear in error-handler output. Lowered for case-insensitive match.
_STACK_TRACE_PHRASES: tuple[str, ...] = (
    "traceback (most recent call last)",
    "stack trace:",
    "exception in thread",
    "at org.",  # Java stack frame "at org.<package>.Class.method"
    "at java.",
    "at com.",
)

# Absolute-path leak patterns. `File "/foo/bar"` is Python's traceback
# format. `/home|/usr|...` catches generic absolute Unix paths. The
# `vendor/`/`node_modules/` pair surfaces package-relative paths even
# when the root prefix is stripped.
_ABS_PATH_FILE_QUOTE = re.compile(r'\bFile "/[^"\s]+"')
_ABS_PATH_UNIX_ROOT = re.compile(
    r"(?<![\w/])(/(?:home|usr|var|opt|app|root)/[\w./-]+)"
)
_PACKAGE_PATH = re.compile(r"\b(?:vendor|node_modules)/")


def find_stack_trace_markers(body: str) -> list[str]:
    """Return a list of spec leaked_data_classes labels for stack
    traces and absolute paths in `body`. Subset of {`stack_trace`,
    `absolute_path`} per spec §Persistence."""
    if not body:
        return []
    lowered = body.lower()
    out: list[str] = []
    if any(p in lowered for p in _STACK_TRACE_PHRASES):
        out.append("stack_trace")
    if (
        _ABS_PATH_FILE_QUOTE.search(body)
        or _ABS_PATH_UNIX_ROOT.search(body)
        or _PACKAGE_PATH.search(body)
    ):
        out.append("absolute_path")
    return out


# Secret-like key names: presence alone implies leaked credentials
# even without inspecting the value. Spec §Strong indicators env/
# config leak markers.
_SECRET_KEY_TOKENS: tuple[str, ...] = (
    "secret_key",
    "api_key",
    "apikey",
    "password",
    "db_password",
    "database_url",
    "redis_url",
    "aws_access_key_id",
    "aws_secret_access_key",
    "private_key",
)

# Pure env-var indicators: keys that prove the page is dumping the
# runtime environment but aren't themselves secret-shaped.
_ENV_ONLY_TOKENS: tuple[str, ...] = (
    "app_env",
    "node_env",
    "debug=true",
)

# Every secret-key token is also an env var when it appears on a
# debug page (it's a runtime environment variable that happens to
# carry a secret). Compose explicitly so the dual-label intent is
# visible in the data instead of an accidental copy-paste duplicate.
_ENV_KEY_TOKENS: tuple[str, ...] = _ENV_ONLY_TOKENS + _SECRET_KEY_TOKENS


def find_env_leak_markers(body: str) -> list[str]:
    """Return a list of spec leaked_data_classes labels for env
    variables and secret-like values in `body`. Subset of
    {`environment_variable`, `secret_like_value`}."""
    if not body:
        return []
    lowered = body.lower()
    out: list[str] = []
    if any(token in lowered for token in _SECRET_KEY_TOKENS):
        out.append("secret_like_value")
    if any(token in lowered for token in _ENV_KEY_TOKENS):
        out.append("environment_variable")
    return out
