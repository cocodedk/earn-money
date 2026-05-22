"""Codex P2.1 — bucket rebuild when the program's effective rate-
limit cap changes (operator edits `roe.md::max_requests_per_second`
while workers stay up).
"""
from __future__ import annotations

from apps.programs.loader import Program
from apps.programs.rate_limit import _bucket_for, _reset_for_tests
from apps.programs.roe import RoE
from apps.programs.scope import Scope


def _program(*, rps: int, slug: str = "algolia") -> Program:
    return Program(
        platform="hackerone", slug=slug,
        scope=Scope(
            platform="hackerone", slug=slug, policy="rate-limited-OK",
            in_scope=["x.example"], out_of_scope=[],
        ),
        roe=RoE(max_requests_per_second=rps),
    )


def test_bucket_rebuilt_when_cap_lowered() -> None:
    """Operator lowers `max_requests_per_second` in roe.md → next
    `_bucket_for` returns a fresh bucket at the new lower cap, not
    the cached one at the old higher cap."""
    _reset_for_tests()
    prog_high = _program(rps=8)
    b_high = _bucket_for(prog_high)
    assert b_high.capacity == 8.0
    prog_low = _program(rps=2)
    b_low = _bucket_for(prog_low)
    assert b_low.capacity == 2.0
    assert b_low is not b_high


def test_bucket_rebuilt_when_cap_raised() -> None:
    """Cap raised → bucket replaced with the higher-capacity one
    (subject to the shared floor)."""
    _reset_for_tests()
    prog_low = _program(rps=2)
    b_low = _bucket_for(prog_low)
    assert b_low.capacity == 2.0
    prog_high = _program(rps=5)
    b_high = _bucket_for(prog_high)
    assert b_high.capacity == 5.0
    assert b_high is not b_low


def test_bucket_reused_when_cap_unchanged() -> None:
    """Two consecutive `_bucket_for` calls at the same effective cap
    return the SAME bucket instance (running token state preserved)."""
    _reset_for_tests()
    prog = _program(rps=3)
    b1 = _bucket_for(prog)
    b2 = _bucket_for(prog)
    assert b1 is b2
