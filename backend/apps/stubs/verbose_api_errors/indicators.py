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


Kind = Literal["json_debug_field", "source_path", "database_error"]


class ApiErrorIndicator(NamedTuple):
    kind: Kind
    matched_value: str  # bounded snippet for evidence excerpt


# Strong-disclosure JSON field NAMES (case-sensitive — frameworks
# emit these exact keys). Spec §"Strong disclosure indicators":
# stack/trace fields + exception fields + source location fields.
_STRONG_JSON_FIELDS: frozenset[str] = frozenset({
    "stack", "trace", "stackTrace", "traceback", "frames", "backtrace",
    "exception", "exceptionClass", "errorClass",
    "file", "filename", "line", "lineNumber", "column",
})

# Source-path patterns: an absolute path on Unix or Windows that
# carries a language-extension line/column suffix. Conservative —
# bare paths without a `:line` or filename pattern miss the bar.
_SOURCE_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    # /<dir>/<file>.<lang-ext>:<digits>
    re.compile(
        r"(?:/(?:app|srv|var|home|usr|opt)/[^\s'\"<>]+"
        r"\.(?:py|js|mjs|ts|tsx|java|cs|php|rb|go|rs)(?::\d+)?)",
    ),
    # node_modules / vendor / site-packages paths
    re.compile(
        r"(?:[^\s'\"<>]*?(?:node_modules|site-packages|vendor)/"
        r"[^\s'\"<>]+\.(?:js|mjs|py|php|rb)(?::\d+(?::\d+)?)?)",
    ),
    # Windows drive paths with .cs:line / .vb:line suffix
    re.compile(
        r"(?:[A-Za-z]:\\\\?[^\s'\"<>]+"
        r"\.(?:cs|vb|fs|py|js)(?::line\s*\d+)?)",
    ),
    # Java frame shape: `File.java:42` (often inside parens)
    re.compile(r"\b[A-Z][A-Za-z0-9_]+\.java:\d+\b"),
)

# Database engine error signatures. Each entry is a strong, vendor-
# specific anchor — generic words like "error" don't qualify.
_DATABASE_ERROR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bSQLSTATE\s*\d+", re.IGNORECASE),
    re.compile(r"\bORA-\d{4,5}\b"),
    re.compile(r"\bpsycopg(?:2|3)?\.errors\.[A-Za-z]+"),
    re.compile(
        r"You have an error in your SQL syntax",
        re.IGNORECASE,
    ),
    re.compile(r"\bsqlite3\.[A-Za-z]*Error\b"),
    re.compile(r"\bno such table:\s+\w+", re.IGNORECASE),
    re.compile(r"\bMicrosoft SQL Server\b.*\berror\b", re.IGNORECASE),
    re.compile(r"\bMongo(?:Network|Server|Write|)Error\b"),
)


def detect_api_error_indicators(
    body: str, content_type: str,
) -> list[ApiErrorIndicator]:
    if not body:
        return []
    indicators: list[ApiErrorIndicator] = []
    json_match = _first_json_field(body, content_type)
    if json_match is not None:
        indicators.append(json_match)
    src_match = _first_match(_SOURCE_PATH_PATTERNS, body)
    if src_match is not None:
        indicators.append(
            ApiErrorIndicator(kind="source_path", matched_value=src_match)
        )
    db_match = _first_match(_DATABASE_ERROR_PATTERNS, body)
    if db_match is not None:
        indicators.append(
            ApiErrorIndicator(kind="database_error", matched_value=db_match)
        )
    return indicators


def _first_json_field(
    body: str, content_type: str,
) -> ApiErrorIndicator | None:
    if "json" not in content_type.lower():
        return None
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None
    return _walk_for_strong_field(data)


def _walk_for_strong_field(node) -> ApiErrorIndicator | None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in _STRONG_JSON_FIELDS and _is_meaningful(value):
                return ApiErrorIndicator(
                    kind="json_debug_field",
                    matched_value=f"{key}={_excerpt(value)}",
                )
            found = _walk_for_strong_field(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for v in node:
            found = _walk_for_strong_field(v)
            if found is not None:
                return found
    return None


def _is_meaningful(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _excerpt(value: object, *, cap: int = 120) -> str:
    return str(value)[:cap]


def _first_match(
    patterns: tuple[re.Pattern[str], ...], body: str,
) -> str | None:
    for pattern in patterns:
        match = pattern.search(body)
        if match is not None:
            return match.group(0)
    return None
