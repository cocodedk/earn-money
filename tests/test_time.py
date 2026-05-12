"""Tests for the central now_iso() helper."""
from __future__ import annotations

import re
from datetime import UTC, datetime

from earn_money._time import now_iso, to_iso


def test_now_iso_uses_z_suffix() -> None:
    s = now_iso()
    assert s.endswith("Z"), s
    assert "+00:00" not in s


def test_now_iso_has_seconds_precision_and_iso_shape() -> None:
    s = now_iso()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", s), s


def test_now_iso_sorts_lexically_with_other_z_timestamps() -> None:
    """Audit-log timestamps must sort by string compare; verify against a known earlier value."""
    s = now_iso()
    assert s > "2026-05-12T00:00:00Z"


def test_to_iso_formats_arbitrary_utc_datetime() -> None:
    dt = datetime(2026, 5, 12, 22, 5, 0, tzinfo=UTC)
    assert to_iso(dt) == "2026-05-12T22:05:00Z"
