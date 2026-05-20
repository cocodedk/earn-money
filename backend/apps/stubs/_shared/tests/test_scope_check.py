"""Contract tests for `_shared/scope_check.enforce_scope`.

Coverage matrix per [[plan slice E]]:
- Cross-origin URL raises OutOfScope.
- Hostless / non-HTTP URL raises OutOfScope (after wrapping ValueError).
- In-scope URL passes silently.
- Out-of-scope deny-list overrides in-scope (negative-scope-is-gospel).
- `OUT_OF_SCOPE_REJECTED` event emitted exactly once per
  (scan_run, candidate_url) — idempotent.
- Event omitted when `scan_run=None` (still raises).
- Event payload includes platform / program_slug / target_url /
  candidate_url / stub_id / reason.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.test import TestCase

from apps.events.models import Event
from apps.events.types import EventType
from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program
from apps.programs.roe import RoE
from apps.programs.scope import Scope
from apps.stubs._shared.scope_check import (
    _reset_emit_cache_for_tests, enforce_scope,
)
from apps.stubs._test_factories import seed_target_run


def _program(in_scope: list[str] | None = None,
             out_of_scope: list[str] | None = None) -> Program:
    in_scope = in_scope if in_scope is not None else ["www.algolia.com", "*.algolia.net"]
    out_of_scope = out_of_scope or []
    return Program(
        platform="hackerone", slug="algolia",
        scope=Scope(
            platform="hackerone", slug="algolia",
            policy="rate-limited-OK",
            in_scope=in_scope, out_of_scope=out_of_scope,
        ),
        roe=RoE(max_requests_per_second=10),
    )


# --- in/out-of-scope ---


def test_enforce_scope_passes_in_scope() -> None:
    _reset_emit_cache_for_tests()
    target = MagicMock(base_url="https://www.algolia.com")
    # No exception — return None.
    assert enforce_scope(target, "https://www.algolia.com/health", _program()) is None


def test_enforce_scope_passes_wildcard_in_scope() -> None:
    _reset_emit_cache_for_tests()
    target = MagicMock(base_url="https://www.algolia.com")
    assert enforce_scope(
        target, "https://api.algolia.net/v2/index", _program(),
    ) is None


def test_enforce_scope_raises_cross_origin() -> None:
    _reset_emit_cache_for_tests()
    target = MagicMock(base_url="https://www.algolia.com")
    with pytest.raises(OutOfScope, match="not in program scope"):
        enforce_scope(target, "https://attacker.example.com/", _program())


def test_enforce_scope_respects_out_of_scope_deny_list() -> None:
    _reset_emit_cache_for_tests()
    target = MagicMock(base_url="https://www.algolia.com")
    prog = _program(in_scope=["*.algolia.net"], out_of_scope=["blocked.algolia.net"])
    with pytest.raises(OutOfScope, match="out_of_scope"):
        enforce_scope(target, "https://blocked.algolia.net/", prog)


def test_enforce_scope_rejects_non_http_scheme() -> None:
    _reset_emit_cache_for_tests()
    target = MagicMock(base_url="https://www.algolia.com")
    with pytest.raises(OutOfScope, match="malformed"):
        enforce_scope(target, "ftp://www.algolia.com/", _program())


def test_enforce_scope_rejects_hostless_url() -> None:
    _reset_emit_cache_for_tests()
    target = MagicMock(base_url="https://www.algolia.com")
    with pytest.raises(OutOfScope, match="malformed"):
        enforce_scope(target, "https:///just/a/path", _program())


# --- event emission ---


class EventEmissionTests(TestCase):
    """Need DB for Event.log() to persist."""

    def setUp(self) -> None:
        _reset_emit_cache_for_tests()
        self.scan_run, self.target_run = seed_target_run(
            stub_slug="1.20", host="www.algolia.com",
        )
        self.target = self.target_run.target

    def test_emits_event_when_scan_run_supplied(self) -> None:
        with pytest.raises(OutOfScope):
            enforce_scope(
                self.target, "https://evil.example.com/x",
                _program(), scan_run=self.scan_run, stub_id="1.20",
            )
        events = list(Event.objects.filter(
            scan_run=self.scan_run, type=EventType.OUT_OF_SCOPE_REJECTED,
        ))
        assert len(events) == 1
        payload = events[0].data
        assert payload["platform"] == "hackerone"
        assert payload["program_slug"] == "algolia"
        assert payload["target_url"] == "https://www.algolia.com"
        assert payload["candidate_url"] == "https://evil.example.com/x"
        assert payload["stub_id"] == "1.20"
        assert "reason" in payload

    def test_idempotent_emit_per_scan_run_and_candidate(self) -> None:
        """Two consecutive rejections of the same (scan_run, candidate)
        emit exactly one event."""
        for _ in range(3):
            with pytest.raises(OutOfScope):
                enforce_scope(
                    self.target, "https://evil.example.com/x",
                    _program(), scan_run=self.scan_run,
                )
        assert Event.objects.filter(
            scan_run=self.scan_run, type=EventType.OUT_OF_SCOPE_REJECTED,
        ).count() == 1

    def test_different_candidate_urls_emit_separate_events(self) -> None:
        for url in ("https://evil-a.example/", "https://evil-b.example/"):
            with pytest.raises(OutOfScope):
                enforce_scope(
                    self.target, url, _program(), scan_run=self.scan_run,
                )
        assert Event.objects.filter(
            scan_run=self.scan_run, type=EventType.OUT_OF_SCOPE_REJECTED,
        ).count() == 2

    def test_no_event_when_scan_run_absent(self) -> None:
        with pytest.raises(OutOfScope):
            enforce_scope(
                self.target, "https://evil.example.com/x", _program(),
                scan_run=None,
            )
        assert Event.objects.filter(
            type=EventType.OUT_OF_SCOPE_REJECTED,
        ).count() == 0


def test_emit_cache_evicts_oldest_when_full(monkeypatch) -> None:
    """LRU cache discards the oldest entry once `_EMIT_CACHE_SIZE` is
    exceeded so memory stays bounded across long-lived workers."""
    from apps.stubs._shared import scope_check
    _reset_emit_cache_for_tests()
    monkeypatch.setattr(scope_check, "_EMIT_CACHE_SIZE", 2)
    assert scope_check._has_emitted("run-a", "url-a") is False
    assert scope_check._has_emitted("run-a", "url-b") is False
    # Third insert pushes cache to size 3 → eviction trims to 2.
    assert scope_check._has_emitted("run-a", "url-c") is False
    # url-a was evicted; url-c is the most-recent.
    assert ("run-a", "url-a") not in scope_check._emit_cache
    assert ("run-a", "url-c") in scope_check._emit_cache
