"""Pure-function tests for stub 1.10 classify_probe.

Maps an HTTP probe response → Verdict | None per spec §Response
classification + §Confidence rules + §Finding status.
"""
from __future__ import annotations

import unittest

from apps.findings.models import FindingStatus

from ..classify import classify_probe


def _probe(
    body: str = "",
    *,
    status: int = 200,
    content_type: str = "text/html",
    headers: dict[str, str] | None = None,
    location: str | None = None,
) -> dict:
    return {
        "status": status,
        "body": body,
        "headers": {"content-type": content_type, **(headers or {})},
        "location": location,
    }


class NotFoundTests(unittest.TestCase):
    def test_404_returns_none(self) -> None:
        assert classify_probe("/phpinfo.php", _probe(status=404), "home") is None

    def test_410_returns_none(self) -> None:
        assert classify_probe("/phpinfo.php", _probe(status=410), "home") is None


class GenericFallbackTests(unittest.TestCase):
    def test_baseline_body_match_returns_none(self) -> None:
        # SPA shell / wildcard 200 returning the homepage body for
        # /phpinfo.php — spec §Negative: must not create a finding
        # for an SPA fallback.
        verdict = classify_probe(
            "/phpinfo.php",
            _probe(body="welcome home", status=200),
            "welcome home",
        )
        assert verdict is None


class FrameworkSignatureTests(unittest.TestCase):
    def test_phpinfo_match_yields_confirmed_high(self) -> None:
        body = "<title>phpinfo()</title>\n<h1>PHP Version 8.2</h1>"
        verdict = classify_probe(
            "/phpinfo.php", _probe(body=body, status=200), "home",
        )
        assert verdict is not None
        assert verdict.kind == "phpinfo"
        assert verdict.confidence == "high"
        assert verdict.finding_status == FindingStatus.CONFIRMED
        assert verdict.exposure == "public"

    def test_spring_actuator_json_yields_confirmed_high(self) -> None:
        body = '{"_links":{"self":{"href":"/actuator"},"health":{"href":"/x"}}}'
        verdict = classify_probe(
            "/actuator",
            _probe(body=body, status=200, content_type="application/json"),
            "home",
        )
        assert verdict is not None
        assert verdict.kind == "spring_actuator"


class EnvLeakTests(unittest.TestCase):
    def test_env_leak_alone_yields_environment_leak_kind(self) -> None:
        body = "SECRET_KEY=xxx\nDATABASE_URL=postgres://u:p@h/d\nDEBUG=True"
        verdict = classify_probe(
            "/actuator/env",
            _probe(body=body, status=200, content_type="application/json"),
            "home",
        )
        assert verdict is not None
        assert verdict.kind == "environment_leak"
        assert verdict.confidence == "high"
        assert verdict.finding_status == FindingStatus.CONFIRMED
        assert "secret_like_value" in verdict.leaked_data_classes
        assert "environment_variable" in verdict.leaked_data_classes


class StackTraceTests(unittest.TestCase):
    def test_python_traceback_yields_stack_trace_kind(self) -> None:
        body = (
            "Traceback (most recent call last):\n"
            '  File "/app/views.py", line 12, in handle\n    raise ValueError'
        )
        verdict = classify_probe(
            "/debug", _probe(body=body, status=500), "home",
        )
        assert verdict is not None
        assert verdict.kind == "stack_trace"
        assert verdict.confidence == "high"
        assert "stack_trace" in verdict.leaked_data_classes
        assert "absolute_path" in verdict.leaked_data_classes


class AuthBoundaryTests(unittest.TestCase):
    def test_401_on_high_signal_path_yields_candidate_medium(self) -> None:
        verdict = classify_probe(
            "/actuator/env",
            _probe(body="unauthorized", status=401),
            "home",
        )
        assert verdict is not None
        assert verdict.finding_status == FindingStatus.CANDIDATE
        assert verdict.confidence == "medium"
        assert verdict.exposure == "blocked"
        assert verdict.kind == "spring_actuator"

    def test_403_on_phpinfo_path_yields_candidate_medium(self) -> None:
        verdict = classify_probe(
            "/phpinfo.php", _probe(body="forbidden", status=403), "home",
        )
        assert verdict is not None
        assert verdict.kind == "phpinfo"
        assert verdict.exposure == "blocked"
        assert verdict.confidence == "medium"

    def test_401_on_non_signal_path_returns_none(self) -> None:
        # Random 401 isn't a debug-page finding — needs a high-signal
        # path or body evidence.
        assert classify_probe(
            "/api/users", _probe(body="unauthorized", status=401), "home",
        ) is None


class GenericLivePathTests(unittest.TestCase):
    def test_200_on_high_signal_path_without_body_evidence_returns_none(
        self,
    ) -> None:
        # Spec §Negative: "must not confirm /status, /health, or /info
        # based on path and 200 status alone." A 200 without body
        # markers must not yield a confirmed finding. MVP returns None
        # entirely; weak-candidate emission is deferred.
        verdict = classify_probe(
            "/server-status",
            _probe(body="<h1>Generic admin page</h1>", status=200),
            "home",
        )
        assert verdict is None

    def test_generic_200_yields_none(self) -> None:
        verdict = classify_probe(
            "/debug/vars", _probe(body="<h1>Hello</h1>", status=200), "home",
        )
        assert verdict is None


class EmptyBodyTests(unittest.TestCase):
    def test_empty_body_status_200_on_high_signal_path_returns_none(
        self,
    ) -> None:
        verdict = classify_probe(
            "/_profiler/", _probe(body="", status=200), "home",
        )
        assert verdict is None
