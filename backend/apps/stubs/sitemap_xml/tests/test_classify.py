"""Pure-function tests for stub 1.12 classify_response."""
from __future__ import annotations

import unittest

from apps.findings.models import FindingStatus

from ..classify import FetchOutcome, classify_response
from ..parser import ParsedSitemap, SitemapEntry


def _ok(status: int = 200, body: str = "<urlset></urlset>") -> FetchOutcome:
    return FetchOutcome(
        kind="ok", status=status, body=body,
        final_url="https://x.example/sitemap.xml",
    )


def _parsed(kind: str = "urlset", entries: int = 1) -> ParsedSitemap:
    return ParsedSitemap(
        kind=kind,  # type: ignore[arg-type]
        entries=tuple(
            SitemapEntry(loc=f"https://x.example/{i}")
            for i in range(entries)
        ),
    )


class UrlsetTests(unittest.TestCase):
    def test_200_urlset_yields_confirmed_high(self) -> None:
        verdict = classify_response(_ok(), parsed=_parsed("urlset", 3))
        assert verdict.classification == "sitemap_present"
        assert verdict.finding_status == FindingStatus.CONFIRMED
        assert verdict.confidence == "high"

    def test_200_empty_urlset_yields_confirmed_high(self) -> None:
        # An empty <urlset> is a valid (if useless) sitemap; the
        # classifier shouldn't reject it.
        verdict = classify_response(
            _ok(), parsed=_parsed("urlset", 0),
        )
        assert verdict.classification == "sitemap_present"
        assert verdict.finding_status == FindingStatus.CONFIRMED


class SitemapIndexTests(unittest.TestCase):
    def test_200_sitemapindex_yields_confirmed_high(self) -> None:
        verdict = classify_response(
            _ok(), parsed=_parsed("sitemapindex", 2),
        )
        assert verdict.classification == "sitemap_index_present"
        assert verdict.confidence == "high"


class ParseErrorTests(unittest.TestCase):
    def test_200_with_unknown_kind_yields_parse_error_candidate(self) -> None:
        verdict = classify_response(
            _ok(body="<html>not a sitemap</html>"),
            parsed=_parsed("unknown", 0),
        )
        assert verdict.classification == "sitemap_parse_error"
        assert verdict.finding_status == FindingStatus.CANDIDATE
        assert verdict.confidence == "low"

    def test_200_with_empty_body_yields_parse_error(self) -> None:
        verdict = classify_response(
            FetchOutcome(
                kind="ok", status=200, body="",
                final_url="https://x.example/sitemap.xml",
            ),
            parsed=_parsed("unknown", 0),
        )
        assert verdict.classification == "sitemap_parse_error"


class NotFoundTests(unittest.TestCase):
    def test_404_yields_rejected(self) -> None:
        verdict = classify_response(_ok(status=404, body=""), parsed=None)
        assert verdict.classification == "not_found"
        assert verdict.finding_status == FindingStatus.REJECTED

    def test_410_yields_rejected(self) -> None:
        verdict = classify_response(_ok(status=410, body=""), parsed=None)
        assert verdict.classification == "not_found"


class ProtectedTests(unittest.TestCase):
    def test_401_yields_candidate_medium(self) -> None:
        verdict = classify_response(_ok(status=401, body=""), parsed=None)
        assert verdict.classification == "protected"
        assert verdict.finding_status == FindingStatus.CANDIDATE
        assert verdict.confidence == "medium"

    def test_403_yields_candidate_medium(self) -> None:
        verdict = classify_response(_ok(status=403, body=""), parsed=None)
        assert verdict.classification == "protected"


class ServerErrorTests(unittest.TestCase):
    def test_5xx_yields_fetch_error_candidate_low(self) -> None:
        verdict = classify_response(_ok(status=502, body=""), parsed=None)
        assert verdict.classification == "sitemap_fetch_error"
        assert verdict.finding_status == FindingStatus.CANDIDATE
        assert verdict.confidence == "low"


class TooLargeTests(unittest.TestCase):
    def test_too_large_kind_yields_candidate_low(self) -> None:
        outcome = FetchOutcome(
            kind="too_large", status=None, body="",
            final_url="https://x.example/sitemap.xml",
        )
        verdict = classify_response(outcome, parsed=None)
        assert verdict.classification == "sitemap_too_large"
        assert verdict.finding_status == FindingStatus.CANDIDATE
        assert verdict.confidence == "low"


class UnreachableTests(unittest.TestCase):
    def test_unreachable_yields_rejected_low(self) -> None:
        outcome = FetchOutcome(
            kind="unreachable", status=None, body="",
            final_url="https://x.example/sitemap.xml",
        )
        verdict = classify_response(outcome, parsed=None)
        assert verdict.classification == "sitemap_fetch_error"
        assert verdict.finding_status == FindingStatus.REJECTED
        assert verdict.confidence == "low"


class ClientErrorTests(unittest.TestCase):
    def test_other_4xx_yields_rejected(self) -> None:
        verdict = classify_response(_ok(status=418, body=""), parsed=None)
        assert verdict.classification == "client_error"
        assert verdict.finding_status == FindingStatus.REJECTED
