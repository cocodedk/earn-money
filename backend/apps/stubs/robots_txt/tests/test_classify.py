"""Pure-function tests for stub 1.11 classify_response.

Maps an HTTP outcome → Verdict per spec §Response classification +
§Confidence rules + §Finding status.
"""
from __future__ import annotations

import unittest

from apps.findings.models import FindingStatus

from ..classify import FetchOutcome, classify_response


def _ok(status: int = 200, body: str = "User-agent: *\nDisallow: /admin") -> FetchOutcome:
    return FetchOutcome(
        kind="ok",
        status=status,
        body=body,
        final_url="https://example.com/robots.txt",
    )


class PresentTests(unittest.TestCase):
    def test_200_with_body_yields_present_confirmed_high(self) -> None:
        verdict = classify_response(_ok())
        assert verdict.classification == "present"
        assert verdict.finding_status == FindingStatus.CONFIRMED
        assert verdict.confidence == "high"


class EmptyTests(unittest.TestCase):
    def test_200_empty_body_yields_empty_confirmed_high(self) -> None:
        verdict = classify_response(_ok(body=""))
        assert verdict.classification == "empty"
        assert verdict.finding_status == FindingStatus.CONFIRMED
        assert verdict.confidence == "high"

    def test_200_whitespace_only_body_yields_empty(self) -> None:
        verdict = classify_response(_ok(body="   \n\t\n"))
        assert verdict.classification == "empty"

    def test_204_yields_empty(self) -> None:
        verdict = classify_response(_ok(status=204, body=""))
        assert verdict.classification == "empty"
        assert verdict.finding_status == FindingStatus.CONFIRMED


class ProtectedTests(unittest.TestCase):
    def test_401_yields_protected_candidate_medium(self) -> None:
        verdict = classify_response(_ok(status=401, body=""))
        assert verdict.classification == "protected"
        assert verdict.finding_status == FindingStatus.CANDIDATE
        assert verdict.confidence == "medium"

    def test_403_yields_protected_candidate_medium(self) -> None:
        verdict = classify_response(_ok(status=403, body=""))
        assert verdict.classification == "protected"
        assert verdict.finding_status == FindingStatus.CANDIDATE
        assert verdict.confidence == "medium"


class NotFoundTests(unittest.TestCase):
    def test_404_yields_not_found_rejected(self) -> None:
        verdict = classify_response(_ok(status=404, body=""))
        assert verdict.classification == "not_found"
        assert verdict.finding_status == FindingStatus.REJECTED

    def test_410_yields_not_found_rejected(self) -> None:
        verdict = classify_response(_ok(status=410, body=""))
        assert verdict.classification == "not_found"
        assert verdict.finding_status == FindingStatus.REJECTED


class ClientErrorTests(unittest.TestCase):
    def test_other_4xx_yields_client_error_no_confirmed(self) -> None:
        verdict = classify_response(_ok(status=418, body=""))
        assert verdict.classification == "client_error"
        # Spec: "No confirmed finding" — render as REJECTED so the
        # operator can see it didn't succeed.
        assert verdict.finding_status == FindingStatus.REJECTED


class ServerErrorTests(unittest.TestCase):
    def test_5xx_yields_server_error_candidate_low(self) -> None:
        verdict = classify_response(_ok(status=503, body=""))
        assert verdict.classification == "server_error"
        assert verdict.finding_status == FindingStatus.CANDIDATE
        assert verdict.confidence == "low"


class RedirectLimitTests(unittest.TestCase):
    def test_redirect_limit_yields_candidate_low(self) -> None:
        outcome = FetchOutcome(
            kind="redirect_limit", status=None, body="",
            final_url="https://example.com/r2",
        )
        verdict = classify_response(outcome)
        assert verdict.classification == "redirect_limit_exceeded"
        assert verdict.finding_status == FindingStatus.CANDIDATE
        assert verdict.confidence == "low"


class CrossOriginBlockedTests(unittest.TestCase):
    def test_cross_origin_redirect_blocked_yields_candidate_low(self) -> None:
        outcome = FetchOutcome(
            kind="cross_origin_blocked", status=None, body="",
            final_url="https://other.example/robots.txt",
        )
        verdict = classify_response(outcome)
        assert verdict.classification == "cross_origin_redirect_blocked"
        assert verdict.finding_status == FindingStatus.CANDIDATE
        assert verdict.confidence == "low"


class UnreachableTests(unittest.TestCase):
    def test_network_error_yields_unreachable_no_confirmed(self) -> None:
        outcome = FetchOutcome(
            kind="unreachable", status=None, body="",
            final_url="https://example.com/robots.txt",
        )
        verdict = classify_response(outcome)
        assert verdict.classification == "unreachable"
        # Per spec: "no confirmed finding" — REJECTED keeps the
        # operator-visible record without claiming a positive.
        assert verdict.finding_status == FindingStatus.REJECTED
        assert verdict.confidence == "low"


class RedirectedTests(unittest.TestCase):
    def test_200_after_same_origin_redirect_keeps_present(self) -> None:
        # Spec §"Redirect classification: same-origin redirect →
        # continue classification on final response". The runner
        # already followed the redirect by the time classify is
        # called; classify sees an ok outcome with a different
        # final_url. Indicator notes the redirect.
        outcome = FetchOutcome(
            kind="ok", status=200,
            body="User-agent: *\nDisallow: /admin",
            final_url="https://example.com/static/robots.txt",
            redirected=True,
        )
        verdict = classify_response(outcome)
        assert verdict.classification == "present"
        assert verdict.confidence == "high"
        assert "redirected" in verdict.indicators
