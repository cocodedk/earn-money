"""Negative + JSON-walker + frame-absent + contract tests for the
stub 1.16 matcher. Mirrors spec §"Pass/fail check" negative
assertions and the dataclass contract."""
from __future__ import annotations

import unittest

from ..matcher import StackTraceMatch, detect_stack_traces


class NegativeTests(unittest.TestCase):
    def test_generic_500_message_no_finding(self) -> None:
        body = (
            "<html><body><h1>500 Internal Server Error</h1>"
            "<p>An unexpected error occurred.</p></body></html>"
        )
        assert detect_stack_traces(body, "text/html") == []

    def test_normal_404_page_no_finding(self) -> None:
        body = "<html><body><h1>404 Not Found</h1></body></html>"
        assert detect_stack_traces(body, "text/html") == []

    def test_stack_trace_words_without_frames_no_finding(self) -> None:
        body = (
            "<p>Please include the full stack trace when filing "
            "a bug report.</p>"
        )
        assert detect_stack_traces(body, "text/html") == []

    def test_empty_body_returns_empty(self) -> None:
        assert detect_stack_traces("", "text/html") == []


class JsonHaystackTests(unittest.TestCase):
    def test_invalid_json_falls_back_to_body_scan(self) -> None:
        # CT says JSON but body isn't parseable — the matcher must
        # still scan the raw body so a near-miss doesn't blind it.
        body = (
            "Traceback (most recent call last):\n"
            '  File "/x.py", line 1, in run\n'
            "ValueError: x\n"
        )
        matches = detect_stack_traces(body, "application/json")
        assert any(m.family == "python_traceback" for m in matches)

    def test_json_with_numeric_value_no_crash(self) -> None:
        # Non-string JSON leaves (numbers, bools, null) are walked
        # past harmlessly — they have no string content to scan.
        body = (
            '{"status": 500, "stack": "Traceback (most recent call last):'
            '\\n  File \\"/x.py\\", line 1, in run", "ok": false, "n": null}'
        )
        matches = detect_stack_traces(body, "application/json")
        assert any(m.family == "python_traceback" for m in matches)

    def test_json_array_walked(self) -> None:
        # The flattener recurses into list values too — a JSON
        # array containing trace strings must still produce a match.
        body = (
            '["Traceback (most recent call last):", '
            '"  File \\"/x.py\\", line 1, in run", '
            '"ValueError: x"]'
        )
        matches = detect_stack_traces(body, "application/json")
        assert any(m.family == "python_traceback" for m in matches)


class FrameAbsentTests(unittest.TestCase):
    def test_whitelabel_without_java_frames_top_frame_is_none(self) -> None:
        # Spring's Whitelabel Error Page can land with no Java stack
        # frames (HTML-only error). The family must still surface
        # but with top_frame=None + stack_frame_count=0.
        body = "<html><body>Whitelabel Error Page</body></html>"
        matches = detect_stack_traces(body, "text/html")
        spring = next(m for m in matches if m.family == "spring_boot_error")
        assert spring.top_frame is None
        assert spring.stack_frame_count == 0


class DedupePerFamilyTests(unittest.TestCase):
    def test_match_emitted_once_when_raw_and_json_both_hit(self) -> None:
        # A pretty-printed JSON body where the python_traceback
        # signature matches BOTH the raw bytes (unescaped newlines)
        # AND the flattened string view. Each family must surface
        # exactly once — the inner-loop break is the load-bearing
        # invariant for that dedupe.
        body = (
            '{"stack": "Traceback (most recent call last):\\n'
            '  File \\"/x.py\\", line 1, in run\\n'
            'ValueError: x"}'
        )
        matches = detect_stack_traces(body, "application/json")
        python_matches = [
            m for m in matches if m.family == "python_traceback"
        ]
        assert len(python_matches) == 1


class ContractTests(unittest.TestCase):
    def test_returns_namedtuple(self) -> None:
        body = (
            "Traceback (most recent call last):\n"
            '  File "/x.py", line 1, in run\n'
            "ValueError: x\n"
        )
        result = detect_stack_traces(body, "text/html")
        assert isinstance(result[0], StackTraceMatch)
