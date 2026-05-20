"""Per-family classifier for stub `well_known_paths`.

For each `(snapshot, family)` pair: run the family's Signature table,
return the highest-confidence `Verdict` if any signal fires AND the
status code looks legitimate (2xx / 206 partial).

Spec sources: 1.20-1.25 §Classification.
"""
from __future__ import annotations

import re
from typing import NamedTuple, Optional

from apps.findings.models import Severity

from .._shared.types import Confidence
from ._types import Family, Signature


class Verdict(NamedTuple):
    confidence: Confidence
    family: Family
    signature_id: str
    matched_text: str
    severity: str  # Severity.* value


_CONFIDENCE_RANK: dict[Confidence, int] = {"low": 0, "medium": 1, "high": 2}
_OK_STATUSES = (200, 206)


def _matches_signature(sig: Signature, body: bytes) -> Optional[str]:
    """Return the matched substring (decoded) or None."""
    if sig.pattern_type == "magic_bytes":
        prefix_bytes = bytes.fromhex(sig.pattern.replace(" ", ""))
        if body.startswith(prefix_bytes):
            return prefix_bytes.hex(" ")
        return None
    # `regex` pattern type — decode body and search.
    text = body.decode("utf-8", errors="replace")
    flags = re.MULTILINE | (0 if sig.case_sensitive else re.IGNORECASE)
    m = re.search(sig.pattern, text, flags=flags)
    if m is None:
        return None
    return m.group(0)


def classify(
    *,
    status: int,
    body: bytes,
    family: Family,
    signatures: tuple[Signature, ...],
    severity_hint: str,
) -> Optional[Verdict]:
    """Run the family's signatures over `body`. Return the strongest
    Verdict, or None if no signature fires or status is not 2xx/206."""
    if status not in _OK_STATUSES:
        return None
    if not body:
        return None

    best: Optional[Verdict] = None
    best_rank = -1
    for sig in signatures:
        matched = _matches_signature(sig, body)
        if matched is None:
            continue
        rank = _CONFIDENCE_RANK[sig.confidence_hint]
        if rank > best_rank:
            best = Verdict(
                confidence=sig.confidence_hint,
                family=family,
                signature_id=sig.id,
                matched_text=matched[:512],
                severity=_severity_for(sig.confidence_hint, severity_hint),
            )
            best_rank = rank
    return best


def _severity_for(conf: Confidence, family_hint: str) -> str:
    """Spec §Severity guidance: high-confidence hits use the family's
    hint; low-confidence collapses to INFO regardless of hint."""
    if conf == "low":
        return Severity.INFO
    return family_hint
