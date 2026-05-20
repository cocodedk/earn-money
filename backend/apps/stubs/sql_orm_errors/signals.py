"""Body-signature matcher for stub 1.19 sql_orm_errors.

Iterates the typed `SIGNATURES` table, applies each row to the response
body, and returns the strongest match by `confidence_hint` priority
(high > medium > low; ties broken by SIGNATURES order, which is
most-specific-first per spec §Signature sources).

Returns `None` when no signature fires. The classifier (slice 19-B)
turns a `Match` into a `Verdict` with the spec's confidence ladder.

Spec: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/01-information-gathering/19-sql-orm-errors.md
"""
from __future__ import annotations

import re
from typing import NamedTuple, Optional

from .signatures import SIGNATURES, Confidence, Signature


# Confidence-rank used for "strongest" selection. Higher wins.
_CONFIDENCE_RANK: dict[Confidence, int] = {"low": 0, "medium": 1, "high": 2}


class Match(NamedTuple):
    """A single signature hit on a response body.

    `matched_text` is the substring that triggered the match (used by
    the classifier + redactor for snippet extraction). `offset` is the
    byte index into the body where the match started.
    """
    signature: Signature
    matched_text: str
    offset: int


def _compile(sig: Signature) -> re.Pattern[str]:
    """Compile a Signature's pattern into a regex.

    Literal patterns are escaped first so `(`, `[`, `*`, etc. don't
    accidentally turn into regex metacharacters. The `IGNORECASE` flag
    is honored per the spec's per-signature case-sensitivity hint.
    """
    flags = 0 if sig.case_sensitive else re.IGNORECASE
    pattern = sig.pattern if sig.pattern_type == "regex" else re.escape(sig.pattern)
    return re.compile(pattern, flags)


# Pre-compile once at import time so the matcher hot path is cheap.
_COMPILED: tuple[tuple[Signature, re.Pattern[str]], ...] = tuple(
    (s, _compile(s)) for s in SIGNATURES
)


def find_strongest_signal(body: bytes) -> Optional[Match]:
    """Return the highest-priority Match on `body`, or None.

    Decodes the body as UTF-8 with `errors="replace"` per spec — the
    runner already enforces shared byte caps via the fetcher, so the
    matcher never sees full responses larger than
    `max_body_bytes_to_scan`.
    """
    text = body.decode("utf-8", errors="replace")
    best: Optional[Match] = None
    best_rank = -1
    for sig, regex in _COMPILED:
        m = regex.search(text)
        if m is None:
            continue
        rank = _CONFIDENCE_RANK[sig.confidence_hint]
        if rank > best_rank:
            best = Match(signature=sig, matched_text=m.group(0), offset=m.start())
            best_rank = rank
            if best_rank == _CONFIDENCE_RANK["high"]:
                # Can't beat 'high'; short-circuit per spec ordering.
                break
    return best
