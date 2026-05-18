"""Confidence ranking helper.

`Finding.confidence` is a free-form string column (low / medium / high
by cookbook convention). Comparing confidences for max/min requires a
total order — keep the order definition in one place so the runner,
live-tests, and any future triage UI all agree.
"""
from __future__ import annotations


CONFIDENCE_RANK: dict[str, int] = {"low": 1, "medium": 2, "high": 3}


def confidence_rank(value: str) -> int:
    """Return the numeric rank for a confidence string; unknown → 0."""
    return CONFIDENCE_RANK.get(value, 0)


def max_confidence(signatures: list[dict[str, str]]) -> str:
    """Return the highest-ranked confidence value across signatures.

    Each signature must have a `confidence` key whose value is in
    CONFIDENCE_RANK. Used by stub runners that group signatures by
    technology and want to surface the strongest single confidence as
    the Finding's confidence."""
    return max(
        (sig["confidence"] for sig in signatures), key=confidence_rank,
    )
