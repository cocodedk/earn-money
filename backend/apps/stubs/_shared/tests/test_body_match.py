"""Tests for the shared body-marker matchers."""
from __future__ import annotations

import unittest

from ..body_match import (
    contains_all,
    contains_all_lowered,
    contains_any,
    contains_any_lowered,
)


class ContainsAnyTests(unittest.TestCase):
    def test_returns_true_when_one_marker_matches(self) -> None:
        assert contains_any("hello world", ("world", "missing")) is True

    def test_returns_false_when_no_marker_matches(self) -> None:
        assert contains_any("hello world", ("absent", "missing")) is False

    def test_case_insensitive(self) -> None:
        # Markers are expected pre-lowered; the body is lowered
        # internally so mixed-case bodies still match.
        assert contains_any("HELLO World", ("world",)) is True

    def test_empty_body_returns_false(self) -> None:
        assert contains_any("", ("anything",)) is False

    def test_empty_markers_returns_false(self) -> None:
        assert contains_any("hello", ()) is False


class ContainsAllTests(unittest.TestCase):
    def test_returns_true_when_every_marker_matches(self) -> None:
        body = "phpinfo() PHP Version 8.2"
        assert contains_all(body, ("phpinfo()", "php version")) is True

    def test_returns_false_when_any_marker_missing(self) -> None:
        body = "phpinfo() but no version line"
        assert contains_all(body, ("phpinfo()", "php version")) is False

    def test_case_insensitive(self) -> None:
        body = "PHPINFO() PHP VERSION 8"
        assert contains_all(body, ("phpinfo()", "php version")) is True

    def test_empty_body_returns_false(self) -> None:
        # An empty body cannot satisfy any non-empty marker, so the
        # all-quantifier returns False (matches the "no positive
        # signal" intuition).
        assert contains_all("", ("anything",)) is False

    def test_empty_markers_returns_false(self) -> None:
        # Vacuously-true `all([])` would surprise callers — every
        # current call site sets at least one marker. Treat empty
        # markers as "no signal to match" → False.
        assert contains_all("hello", ()) is False


class ContainsAnyLoweredTests(unittest.TestCase):
    def test_matches_against_pre_lowered_body(self) -> None:
        # Caller is responsible for passing a pre-lowered body —
        # the helper does NOT lower internally.
        assert contains_any_lowered("hello world", ("world",)) is True

    def test_uppercase_body_does_not_match(self) -> None:
        # The contract: input is already lowered. A non-lowered
        # body skips the match — this is the intended contract,
        # not a bug.
        assert contains_any_lowered("HELLO WORLD", ("world",)) is False

    def test_empty_lowered_returns_false(self) -> None:
        assert contains_any_lowered("", ("anything",)) is False


class ContainsAllLoweredTests(unittest.TestCase):
    def test_matches_against_pre_lowered_body(self) -> None:
        body = "phpinfo() php version 8.2"
        assert contains_all_lowered(
            body, ("phpinfo()", "php version"),
        ) is True

    def test_missing_marker_returns_false(self) -> None:
        body = "phpinfo() but no version"
        assert contains_all_lowered(
            body, ("phpinfo()", "php version"),
        ) is False

    def test_empty_lowered_returns_false(self) -> None:
        assert contains_all_lowered("", ("anything",)) is False

    def test_empty_markers_returns_false(self) -> None:
        assert contains_all_lowered("hello", ()) is False
