"""False-positive heuristics for stub 1.16.

Spec §"False-positive checks": a status-200 page with docs-like
markers and a sample trace must NOT be confirmed as a stack-trace
finding. The classifier (slice 3) consumes the boolean from
``is_documentation_like`` to downgrade or reject in this case.

A status >= 400 response with a stack trace stays a finding — even
if the body contains the word "example" — per spec ("if a full
runtime stack trace appears in a 500 response, report it even if
the body contains the word `example`").

Spec heuristics 3 and 4 — "matched trace appears inside a code
example block" and "no nearby exception status, request ID,
timestamp, error route, or application error wording" — are
deferred. Per spec §"Heuristics for documentation-like pages":
all four are cumulative signals, so adding these later can only
strengthen the docs-likeness verdict, not change the contract.
Tracked for the slice-3 classifier or a follow-up.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/16-stack-traces.md
"""
from __future__ import annotations

import re


# Status 200 anchor — error responses (4xx/5xx) are application
# territory; only normal 200s qualify as documentation hosts.
_DOCS_STATUS = 200

# Word-bounded markers that signal a docs/tutorial/sample page.
# Bounded by case-insensitive whole-word match so "example.com"
# doesn't flag the keyword "example" — the marker must be a token.
_DOCS_MARKERS_RE = re.compile(
    r"\b(?:documentation|tutorial|readme|example|sample|"
    r"how[- ]?to|guide)\b",
    re.IGNORECASE,
)


def is_documentation_like(body: str, *, status: int) -> bool:
    if status != _DOCS_STATUS:
        return False
    if not body:
        return False
    return _DOCS_MARKERS_RE.search(body) is not None
