"""Regex pattern tables for stub 1.17 strong-disclosure indicators.

Split out of indicators.py to keep both files under the 200-line
cap. The constants are package-internal (imported only by
indicators.py inside the stub) — exported with public names so
the import site reads cleanly without `as _NAME` ceremony.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/17-verbose-api-errors.md
"""
from __future__ import annotations

import re


# Strong-disclosure JSON field NAMES, lowercased — matched case-
# insensitively against the response body's keys. Spec §"Strong
# disclosure indicators": stack/trace + exception + source location.
# Lowercasing the body's keys at walk time lets the matcher catch
# .NET PascalCase emissions (`StackTrace`, `Source`, `InnerException`)
# alongside the typical lowerCamelCase from Node/Python/Java.
STRONG_JSON_FIELDS_LOWER: frozenset[str] = frozenset({
    "stack", "trace", "stacktrace", "traceback", "frames", "backtrace",
    "exception", "exceptionclass", "errorclass",
    "file", "filename", "line", "linenumber", "column",
})


# Per-field matched_value cap. The signature row carries up to
# spec-config max_evidence_excerpt_bytes (4096) for the body
# excerpt; the per-field snippet is one log line so the row stays
# compact when many fields fire.
MATCHED_VALUE_CAP = 120


# Source-path patterns: an absolute path on Unix or Windows that
# carries a language-extension line/column suffix. Conservative —
# bare paths without a `:line` or filename pattern miss the bar.
SOURCE_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
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
DATABASE_ERROR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bSQLSTATE\s*\d+", re.IGNORECASE),
    re.compile(r"\bORA-\d{4,5}\b"),
    re.compile(r"\bpsycopg(?:2|3)?\.errors\.[A-Za-z]+"),
    re.compile(
        r"You have an error in your SQL syntax",
        re.IGNORECASE,
    ),
    re.compile(r"\bsqlite3\.[A-Za-z]*Error\b"),
    re.compile(r"\bno such table:\s+\w+", re.IGNORECASE),
    # Bounded `.{0,200}?` avoids full-body backtracking when the
    # first literal hits early and the second never appears.
    re.compile(
        r"\bMicrosoft SQL Server\b.{0,200}?\berror\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(r"\bMongo(?:Network|Server|Write|)Error\b"),
)
