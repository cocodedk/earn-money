"""Tests for stub 1.17 classifier — spec §"Confidence rules" +
§"Status rules"."""
from __future__ import annotations

import unittest

from ..classifier import Verdict, classify
from ..indicators import ApiErrorIndicator


def _ind(kind: str, value: str = "x") -> ApiErrorIndicator:
    return ApiErrorIndicator(kind=kind, matched_value=value)  # type: ignore[arg-type]


class NoIndicatorsTests(unittest.TestCase):
    def test_empty_returns_none(self) -> None:
        assert classify([], response_status=500) is None


class HighConfirmedTests(unittest.TestCase):
    def test_error_status_with_strong_kind_is_high(self) -> None:
        for kind in ("json_debug_field", "source_path", "database_error"):
            verdict = classify([_ind(kind)], response_status=500)
            assert verdict == Verdict(confidence="high", status="confirmed")

    def test_multiple_strong_kinds_still_high(self) -> None:
        verdict = classify(
            [_ind("json_debug_field"), _ind("database_error")],
            response_status=500,
        )
        assert verdict.confidence == "high"


class MediumConfirmedTests(unittest.TestCase):
    def test_200_json_with_debug_field_is_medium(self) -> None:
        # Developer-mode API errors that didn't bump status — spec
        # §"Confidence rules" §medium third bullet. The matcher only
        # emits `json_debug_field` on JSON CT, so no separate CT
        # check is needed here.
        verdict = classify(
            [_ind("json_debug_field")], response_status=200,
        )
        assert verdict == Verdict(confidence="medium", status="confirmed")

    def test_error_status_with_framework_hint_is_medium(self) -> None:
        # FU-2: spec §"Confidence rules" §medium 2nd bullet — error
        # status + framework hint, no full stack/path → medium.
        verdict = classify(
            [_ind("framework_hint", "django")], response_status=500,
        )
        assert verdict == Verdict(confidence="medium", status="confirmed")

    def test_200_framework_hint_alone_stays_low(self) -> None:
        # No error status → framework hint alone is just a weak
        # fingerprint signal, not a finding-confidence promotion.
        verdict = classify(
            [_ind("framework_hint", "django")], response_status=200,
        )
        assert verdict.confidence == "low"


class LowCandidateTests(unittest.TestCase):
    def test_200_source_path_alone_is_low(self) -> None:
        # Path leak on a non-error response — weak signal, surfaces
        # as candidate so a follow-up probe can promote.
        verdict = classify([_ind("source_path")], response_status=200)
        assert verdict == Verdict(confidence="low", status="candidate")

    def test_200_database_error_alone_is_low(self) -> None:
        verdict = classify([_ind("database_error")], response_status=200)
        assert verdict.confidence == "low"


class ContractTests(unittest.TestCase):
    def test_returns_verdict(self) -> None:
        verdict = classify([_ind("source_path")], response_status=500)
        assert isinstance(verdict, Verdict)
        assert verdict.confidence in ("low", "medium", "high")
        assert verdict.status in (
            "candidate", "confirmed", "rejected", "stale",
        )
