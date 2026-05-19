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
        assert classify(
            [], response_status=500, content_type="application/json",
        ) is None


class HighConfirmedTests(unittest.TestCase):
    def test_error_status_with_strong_kind_is_high(self) -> None:
        for kind in ("json_debug_field", "source_path", "database_error"):
            verdict = classify(
                [_ind(kind)],
                response_status=500, content_type="application/json",
            )
            assert verdict == Verdict(confidence="high", status="confirmed")

    def test_multiple_strong_kinds_still_high(self) -> None:
        verdict = classify(
            [_ind("json_debug_field"), _ind("database_error")],
            response_status=500, content_type="application/json",
        )
        assert verdict.confidence == "high"


class MediumConfirmedTests(unittest.TestCase):
    def test_200_json_with_debug_field_is_medium(self) -> None:
        # Developer-mode API errors that didn't bump status — spec
        # §"Confidence rules" §medium third bullet.
        verdict = classify(
            [_ind("json_debug_field")],
            response_status=200, content_type="application/json",
        )
        assert verdict == Verdict(confidence="medium", status="confirmed")


class LowCandidateTests(unittest.TestCase):
    def test_200_source_path_alone_is_low(self) -> None:
        # Path leak on a non-error response — weak signal, surfaces
        # as candidate so a follow-up probe can promote.
        verdict = classify(
            [_ind("source_path")],
            response_status=200, content_type="text/html",
        )
        assert verdict == Verdict(confidence="low", status="candidate")

    def test_200_database_error_alone_is_low(self) -> None:
        verdict = classify(
            [_ind("database_error")],
            response_status=200, content_type="text/plain",
        )
        assert verdict.confidence == "low"


class ContractTests(unittest.TestCase):
    def test_returns_verdict(self) -> None:
        verdict = classify(
            [_ind("source_path")],
            response_status=500, content_type="text/plain",
        )
        assert isinstance(verdict, Verdict)
        assert verdict.confidence in ("low", "medium", "high")
        assert verdict.status in (
            "candidate", "confirmed", "rejected", "stale",
        )
