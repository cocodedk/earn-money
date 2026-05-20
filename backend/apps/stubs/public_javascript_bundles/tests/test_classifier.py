"""Tests for stub 1.15 classifier.

Spec §5 'Confidence rules' + §6 'Status rules'. The classifier is a
pure function from (fetch_kind, content_type_is_js) → Verdict
(confidence, status). The 'stale' status is runner-applied during
persistence (it requires DB history); classifier returns one of
candidate / confirmed / rejected.
"""
from __future__ import annotations

import unittest

from ..classifier import Verdict, classify


class HighConfidenceTests(unittest.TestCase):
    """`high` = JS response + JS content type + (always)
    HTML-referenced (every 1.15 candidate is parsed from HTML)."""

    def test_ok_with_js_content_type_is_high_confirmed(self) -> None:
        verdict = classify(fetch_kind="ok", content_type_is_js=True)
        assert verdict == Verdict(confidence="high", status="confirmed")


class MediumConfidenceTests(unittest.TestCase):
    """`medium` = JS response BUT content type was missing/generic
    — the fetcher accepted via the URL+body heuristic, not the
    content-type allowlist."""

    def test_ok_with_non_js_content_type_is_medium_confirmed(self) -> None:
        verdict = classify(fetch_kind="ok", content_type_is_js=False)
        assert verdict == Verdict(confidence="medium", status="confirmed")


class LowConfidenceTests(unittest.TestCase):
    """`low` = couldn't fetch, ambiguous response, out of scope, or
    only metadata was available."""

    def test_non_js_is_low_rejected(self) -> None:
        # 200 with text/html or application/json — fetched but not JS.
        verdict = classify(fetch_kind="non_js", content_type_is_js=False)
        assert verdict == Verdict(confidence="low", status="rejected")

    def test_absent_is_low_rejected(self) -> None:
        # 404 / 410 — asset wasn't there. Runner upgrades to "stale"
        # during persistence if a previous signature exists; classifier
        # never returns "stale" on its own.
        verdict = classify(fetch_kind="absent", content_type_is_js=False)
        assert verdict == Verdict(confidence="low", status="rejected")

    def test_blocked_is_low_candidate(self) -> None:
        # 401/403 — couldn't verify; the URL may still be a real JS
        # bundle behind auth, so it stays a candidate, not rejected.
        verdict = classify(fetch_kind="blocked", content_type_is_js=False)
        assert verdict == Verdict(confidence="low", status="candidate")

    def test_inconclusive_is_low_candidate(self) -> None:
        # Transport error, too many redirects, 5xx — retry-class
        # outcomes. Keep as candidate so the next scan can try again.
        verdict = classify(fetch_kind="inconclusive", content_type_is_js=False)
        assert verdict == Verdict(confidence="low", status="candidate")

    def test_not_fetched_is_low_candidate(self) -> None:
        # Candidate discovered but skipped (cross-origin without
        # include_cdn_metadata, or fetch budget exhausted).
        verdict = classify(fetch_kind=None, content_type_is_js=False)
        assert verdict == Verdict(confidence="low", status="candidate")


class ContractTests(unittest.TestCase):
    def test_returns_verdict_dataclass(self) -> None:
        verdict = classify(fetch_kind="ok", content_type_is_js=True)
        assert isinstance(verdict, Verdict)
        assert verdict.confidence == "high"
        assert verdict.status == "confirmed"

    def test_ct_is_js_ignored_when_not_ok(self) -> None:
        # The content-type signal only matters on the success path;
        # on failure/rejection paths, ct_is_js must not change the
        # verdict (since the response was discarded).
        assert classify(
            fetch_kind="blocked", content_type_is_js=True,
        ) == classify(fetch_kind="blocked", content_type_is_js=False)
        assert classify(
            fetch_kind="absent", content_type_is_js=True,
        ) == classify(fetch_kind="absent", content_type_is_js=False)
