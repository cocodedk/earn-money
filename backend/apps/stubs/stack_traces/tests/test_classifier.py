"""Tests for stub 1.16 classifier.

Spec §"Confidence rules" + §"Status rules". The classifier takes
the matcher's output + the response status + the docs-like
heuristic, and returns a typed Verdict (confidence, status), or
None when no matches were found.
"""
from __future__ import annotations

import unittest

from ..classifier import Verdict, classify
from ..matcher import StackTraceMatch


def _match(
    family: str = "java_stack",
    language: str = "java",
    framework: str | None = None,
    exception_type: str | None = "java.lang.NullPointerException",
    top_frame: str | None = "App.run:App.java:42",
    stack_frame_count: int = 2,
) -> StackTraceMatch:
    return StackTraceMatch(
        family=family,  # type: ignore[arg-type]
        language=language,  # type: ignore[arg-type]
        framework=framework,
        exception_type=exception_type,
        top_frame=top_frame,
        stack_frame_count=stack_frame_count,
    )


class NoMatchesTests(unittest.TestCase):
    def test_empty_matches_returns_none(self) -> None:
        # Spec: candidates are emitted only when the matcher hits.
        # An empty match list means "no stack trace evidence" — the
        # runner should not persist a finding.
        assert classify([], response_status=200, is_docs_like=False) is None


class DocsLikeRejectionTests(unittest.TestCase):
    def test_docs_like_match_is_rejected(self) -> None:
        # Spec §"False-positive checks" — a docs-like 200 with a
        # sample trace lands as rejected with a low confidence.
        verdict = classify(
            [_match()], response_status=200, is_docs_like=True,
        )
        assert verdict == Verdict(confidence="low", status="rejected")


class HighConfidenceTests(unittest.TestCase):
    """Spec: `high` = known runtime/framework + (2+ frames OR
    1+ frame plus exception) + error response."""

    def test_known_family_two_frames_500_is_high(self) -> None:
        verdict = classify(
            [_match(stack_frame_count=2)],
            response_status=500, is_docs_like=False,
        )
        assert verdict == Verdict(confidence="high", status="confirmed")

    def test_known_family_one_frame_plus_exception_500_is_high(self) -> None:
        verdict = classify(
            [_match(stack_frame_count=1)],
            response_status=500, is_docs_like=False,
        )
        assert verdict == Verdict(confidence="high", status="confirmed")

    def test_django_debug_with_frames_on_500_is_high(self) -> None:
        verdict = classify(
            [_match(family="django_debug", framework="django",
                    stack_frame_count=3, exception_type="ValueError")],
            response_status=500, is_docs_like=False,
        )
        assert verdict.confidence == "high"


class MediumConfidenceTests(unittest.TestCase):
    """Spec: `medium` = clear exception + 1 frame, OR framework
    debug page with partial frames, OR JSON `stack` field."""

    def test_one_frame_plus_exception_on_200_is_medium(self) -> None:
        # 200 status — not an error response → can't qualify as
        # high. Exception + frame keeps it medium.
        verdict = classify(
            [_match(stack_frame_count=1)],
            response_status=200, is_docs_like=False,
        )
        assert verdict == Verdict(confidence="medium", status="confirmed")

    def test_framework_marker_with_partial_frames(self) -> None:
        # framework set, single frame, no exception — medium.
        verdict = classify(
            [_match(framework="spring", exception_type=None,
                    stack_frame_count=1)],
            response_status=500, is_docs_like=False,
        )
        assert verdict.confidence == "medium"


class LowConfidenceTests(unittest.TestCase):
    """Spec: `low` = absolute path / line leak in error context,
    partial or ambiguous trace."""

    def test_generic_stack_trace_no_exception_no_frame_is_low(self) -> None:
        verdict = classify(
            [_match(family="generic_stack_trace", language="unknown",
                    framework=None, exception_type=None,
                    top_frame=None, stack_frame_count=0)],
            response_status=500, is_docs_like=False,
        )
        assert verdict == Verdict(confidence="low", status="confirmed")

    def test_path_line_leak_only_is_low(self) -> None:
        verdict = classify(
            [_match(family="path_line_leak", language="unknown",
                    framework=None, exception_type=None,
                    top_frame="/srv/app.py:42", stack_frame_count=1)],
            response_status=500, is_docs_like=False,
        )
        assert verdict.confidence == "low"


class StrongestMatchTests(unittest.TestCase):
    def test_strongest_wins_when_multiple_matches(self) -> None:
        # A noisy body with a generic-fallback match AND a Java
        # match — the classifier picks the Java one (more frames +
        # exception + known family).
        matches = [
            _match(family="generic_stack_trace", language="unknown",
                   framework=None, exception_type=None,
                   top_frame="/x:1", stack_frame_count=1),
            _match(family="java_stack", language="java",
                   exception_type="java.lang.RuntimeException",
                   stack_frame_count=3),
        ]
        verdict = classify(
            matches, response_status=500, is_docs_like=False,
        )
        assert verdict == Verdict(confidence="high", status="confirmed")


class ContractTests(unittest.TestCase):
    def test_returns_verdict_dataclass(self) -> None:
        verdict = classify(
            [_match()], response_status=500, is_docs_like=False,
        )
        assert isinstance(verdict, Verdict)
        assert verdict.confidence in ("low", "medium", "high")
        assert verdict.status in ("candidate", "confirmed", "rejected", "stale")
