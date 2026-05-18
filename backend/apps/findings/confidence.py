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
