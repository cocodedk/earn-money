"""Tests for stub 1.16 false-positive heuristics.

Spec §"False-positive checks": detect documentation-like pages so
the classifier can downgrade or reject otherwise-matching stack
traces. A 500 response with a full traceback STILL surfaces — the
heuristic only fires when the evidence is ambiguous.
"""
from __future__ import annotations

import unittest

from ..false_positives import is_documentation_like


class StatusGateTests(unittest.TestCase):
    def test_500_is_not_documentation(self) -> None:
        # Spec: a 5xx is application-error territory; even if the
        # body looks docs-like the heuristic must defer.
        body = "Traceback... documentation example..."
        assert is_documentation_like(body, status=500) is False

    def test_non_200_is_not_documentation(self) -> None:
        assert is_documentation_like("...", status=404) is False
        assert is_documentation_like("...", status=403) is False

    def test_200_without_docs_markers_is_not_documentation(self) -> None:
        # A normal 200 page that happens to contain a trace is not
        # a docs page on status alone.
        assert is_documentation_like(
            "Traceback (most recent call last):\n", status=200,
        ) is False


class DocsMarkerTests(unittest.TestCase):
    def test_documentation_title(self) -> None:
        body = (
            "<title>Documentation — Python tracebacks</title>"
            "<pre>Traceback ...</pre>"
        )
        assert is_documentation_like(body, status=200) is True

    def test_tutorial_marker(self) -> None:
        body = (
            "<h1>Tutorial: handling stack traces</h1>"
            "<pre>Traceback ...</pre>"
        )
        assert is_documentation_like(body, status=200) is True

    def test_readme_marker(self) -> None:
        body = (
            "<h1>README</h1><pre>example stack trace</pre>"
        )
        assert is_documentation_like(body, status=200) is True

    def test_how_to_marker(self) -> None:
        body = "<h1>How to read a Python traceback</h1><pre>...</pre>"
        assert is_documentation_like(body, status=200) is True

    def test_example_marker(self) -> None:
        body = "<h1>Example stack trace</h1><pre>...</pre>"
        assert is_documentation_like(body, status=200) is True

    def test_guide_marker(self) -> None:
        body = "<h1>Guide: debugging</h1><pre>...</pre>"
        assert is_documentation_like(body, status=200) is True


class CaseInsensitiveTests(unittest.TestCase):
    def test_uppercase_marker_detected(self) -> None:
        body = "<title>DOCUMENTATION</title><pre>...</pre>"
        assert is_documentation_like(body, status=200) is True

    def test_mixed_case_marker_detected(self) -> None:
        body = "<title>How To Debug</title><pre>...</pre>"
        assert is_documentation_like(body, status=200) is True


class EmptyBodyTests(unittest.TestCase):
    def test_empty_body_is_not_documentation(self) -> None:
        assert is_documentation_like("", status=200) is False

    def test_short_body_with_no_marker(self) -> None:
        # "404 page" mentions no docs marker → not docs-like.
        assert is_documentation_like("Not found", status=200) is False
