"""API error indicator matcher for stub 1.17 (slice 1).

Detects the spec's "strong disclosure indicators" in HTTP response
bodies:

* json_debug_field — JSON body contains a debug field with non-empty
  content (stack, trace, stackTrace, traceback, frames, backtrace,
  exception, exceptionClass, errorClass, file, filename, line,
  lineNumber, column).
* source_path — body contains an absolute server-side path with a
  language-extension line marker (e.g. /app/main.py:42, C:\\app
  \\Home.cs:line 42, /srv/app/node_modules/x.js:1:1).
* database_error — body contains a deterministic DB-engine error
  signature (SQLSTATE, ORA-, psycopg, MySQL syntax, sqlite3 errors,
  Microsoft SQL Server, MongoDB exception text).

Each match becomes one ``ApiErrorIndicator``. The classifier (slice
2) combines indicators with the response status to assign
confidence + status per spec §"Confidence rules".

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/17-verbose-api-errors.md
"""
from __future__ import annotations

import json
import re
from typing import Literal, NamedTuple

from .framework_hints import detect_framework_hints
from .patterns import (
    DATABASE_ERROR_PATTERNS as _DATABASE_ERROR_PATTERNS,
    MATCHED_VALUE_CAP as _MATCHED_VALUE_CAP,
    SOURCE_PATH_PATTERNS as _SOURCE_PATH_PATTERNS,
    STRONG_JSON_FIELDS_LOWER as _STRONG_JSON_FIELDS_LOWER,
)
from .redaction import redact


Kind = Literal[
    "json_debug_field", "source_path", "database_error", "framework_hint",
]


class ApiErrorIndicator(NamedTuple):
    kind: Kind
    matched_value: str  # bounded snippet for evidence excerpt


def detect_api_error_indicators(
    body: str, content_type: str,
) -> list[ApiErrorIndicator]:
    """First-match-per-kind. Sufficient for the classifier verdict —
    confidence keys on the PRESENCE of any strong-kind indicator.
    The signature builder uses `detect_all_indicators` to populate
    the persisted hint arrays."""
    if not body:
        return []
    indicators: list[ApiErrorIndicator] = []
    first_json = next(_walk_json_fields(body, content_type), None)
    if first_json is not None:
        indicators.append(first_json)
    src = _first_match(_SOURCE_PATH_PATTERNS, body)
    if src is not None:
        indicators.append(ApiErrorIndicator(kind="source_path", matched_value=_excerpt(src)))
    db = _first_match(_DATABASE_ERROR_PATTERNS, body)
    if db is not None:
        indicators.append(ApiErrorIndicator(kind="database_error", matched_value=_excerpt(db)))
    for name in detect_framework_hints(body):
        indicators.append(ApiErrorIndicator(kind="framework_hint", matched_value=name))
    return indicators


def detect_all_indicators(
    body: str, content_type: str,
) -> list[ApiErrorIndicator]:
    """All matches per kind — populates the spec's plural hint
    arrays (`database_hints`, `file_path_hints`, ...). Same walkers
    as the first-match path; just consume all of them."""
    if not body:
        return []
    indicators: list[ApiErrorIndicator] = list(
        _walk_json_fields(body, content_type),
    )
    for pattern in _SOURCE_PATH_PATTERNS:
        for match in pattern.findall(body):
            indicators.append(
                ApiErrorIndicator(kind="source_path", matched_value=_excerpt(match)),
            )
    for pattern in _DATABASE_ERROR_PATTERNS:
        for match in pattern.findall(body):
            indicators.append(
                ApiErrorIndicator(kind="database_error", matched_value=_excerpt(match)),
            )
    for name in detect_framework_hints(body):
        indicators.append(ApiErrorIndicator(kind="framework_hint", matched_value=name))
    return indicators


def _walk_json_fields(body: str, content_type: str):
    """One walker — yield every strong-key indicator. Callers take
    `next(...)` for first-match-per-kind or `list(...)` for all."""
    if "json" not in content_type.lower():
        return
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return
    yield from _walk(data)


def _walk(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if (
                key.lower() in _STRONG_JSON_FIELDS_LOWER
                and _is_meaningful(value)
            ):
                yield ApiErrorIndicator(
                    kind="json_debug_field",
                    matched_value=f"{key}={_excerpt(value)}",
                )
            yield from _walk(value)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _is_meaningful(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _excerpt(value: object) -> str:
    # Redact before capping — cap a scrubbed snippet, not a half-leaked secret.
    return redact(str(value))[:_MATCHED_VALUE_CAP]


def _first_match(
    patterns: tuple[re.Pattern[str], ...], body: str,
) -> str | None:
    for pattern in patterns:
        match = pattern.search(body)
        if match is not None:
            return match.group(0)
    return None
