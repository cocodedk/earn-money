"""Seeded candidate data for stub 1.9 — legacy paths, stale tokens,
and deprecation-marker headers.

MVP scope per spec §Default stale path dictionary: the 20 paths the
spec calls out. Discovered-path filtering and version-shadow
generation are deferred until upstream phases feed `discovered_paths`
into the runner — neither has a wiring contract yet on this platform.

Stale tokens are matched as PATH SEGMENTS not substrings — spec §
Token matching rules: `v1` matches `/api/v1/users` not
`/assets/app.v1.js`; `old` matches `/old/login` not `/products/gold`.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/09-old-endpoints.md
"""
from __future__ import annotations


SEEDED_PATHS: tuple[str, ...] = (
    "/old",
    "/old/",
    "/legacy",
    "/legacy/",
    "/deprecated",
    "/deprecated/",
    "/api/old",
    "/api/legacy",
    "/api/deprecated",
    "/api/v0",
    "/api/v0/",
    "/api/v1",
    "/api/v1/",
    "/v0",
    "/v0/",
    "/v1",
    "/v1/",
    "/rest/v0",
    "/rest/v0/",
    "/rest/v1",
    "/rest/v1/",
)

STALE_TOKENS: tuple[str, ...] = (
    "old",
    "legacy",
    "deprecated",
    "deprecate",
    "sunset",
    "obsolete",
    "retired",
    "eol",
    "end-of-life",
    "v0",
    "v1",
)

DEPRECATION_HEADERS: tuple[str, ...] = (
    "Deprecation",
    "Sunset",
    "Warning",
    "Link",
)
