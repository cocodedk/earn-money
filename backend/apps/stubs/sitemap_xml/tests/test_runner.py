"""Tests for stub 1.12 runner.run — seed iteration + persist."""
from __future__ import annotations

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding, FindingStatus
from apps.stubs._test_factories import seed_target_run

from ..runner import run
from ._helpers import mocked_fetcher, resp


_VALID_URLSET = (
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<url><loc>https://x.example/admin</loc></url>"
    "<url><loc>https://x.example/api/products</loc></url>"
    "<url><loc>https://x.example/blog</loc></url>"
    "<url><loc>https://other.example/external</loc></url>"
    "</urlset>"
)

_SITEMAP_INDEX = (
    "<sitemapindex>"
    "<sitemap><loc>https://x.example/sitemap-a.xml</loc></sitemap>"
    "<sitemap><loc>https://x.example/sitemap-b.xml</loc></sitemap>"
    "</sitemapindex>"
)


def _seed():
    return seed_target_run(stub_slug="1.12", host="x.example")


class UrlsetPresentTests(TestCase):
    def test_finds_sitemap_xml_writes_confirmed_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/sitemap.xml": resp(
                _VALID_URLSET, status_code=200,
                url="https://x.example/sitemap.xml",
            ),
        }):
            run(scan_run, target_run)

        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.confidence == "high"
        data = finding.data
        assert data["finding_type"] == "sitemap_xml"
        assert data["classification"] == "sitemap_present"
        assert data["extracted_url_count"] == 4
        assert data["in_scope_url_count"] == 3
        assert data["out_of_scope_url_count"] == 1
        # admin_hint + api_hint should fire on the in-scope URLs.
        tag_counts = data["tag_counts"]
        assert tag_counts.get("admin_hint", 0) == 1
        assert tag_counts.get("api_hint", 0) == 1


class SitemapIndexTests(TestCase):
    def test_finds_index_writes_confirmed_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/sitemap.xml": resp(
                _SITEMAP_INDEX, status_code=200,
                url="https://x.example/sitemap.xml",
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["classification"] == "sitemap_index_present"
        # The index has 2 child sitemap URLs — surface them as
        # extracted URLs so the operator can see the index shape.
        assert finding.data["extracted_url_count"] == 2


class SeedFallthroughTests(TestCase):
    def test_first_seed_404_second_200_lands(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/sitemap.xml": resp("", status_code=404),
            "/sitemap_index.xml": resp(
                _SITEMAP_INDEX, status_code=200,
                url="https://x.example/sitemap_index.xml",
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.data["classification"] == "sitemap_index_present"

    def test_all_seeds_404_writes_rejected(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({}):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.REJECTED
        assert finding.data["classification"] == "not_found"


class EvidenceLinkTests(TestCase):
    def test_evidence_row_linked_to_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/sitemap.xml": resp(
                _VALID_URLSET, status_code=200,
                url="https://x.example/sitemap.xml",
            ),
        }):
            run(scan_run, target_run)
        evidence = Evidence.objects.get(scan_run=scan_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert str(evidence.id) in finding.data["evidence_ids"]
        assert evidence.url.endswith("/sitemap.xml")


class UnreachableTests(TestCase):
    def test_unreachable_writes_rejected_with_empty_aggregate(self) -> None:
        # When all seed fetches raise transport errors, parsed is
        # None and the runner uses the empty-aggregate shape so
        # Finding.data still has every key the frontend expects.
        import httpx
        scan_run, target_run = _seed()

        def raise_(_url, **_kwargs):
            raise httpx.ConnectError("DNS timeout")

        with mocked_fetcher(get_side_effect=raise_):
            run(scan_run, target_run)

        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.REJECTED
        assert finding.data["classification"] == "sitemap_fetch_error"
        assert finding.data["extracted_url_count"] == 0
        assert finding.data["tag_counts"] == {}


class UnknownScopeUrlTests(TestCase):
    def test_unparseable_loc_skipped_silently(self) -> None:
        # A <loc> value that's neither relative nor a valid URL
        # (e.g. operator junk in the sitemap) classifies as
        # "unknown" — the runner drops it from both in_scope and
        # out_of_scope counts.
        scan_run, target_run = _seed()
        body = (
            "<urlset>"
            "<url><loc>https://x.example/real</loc></url>"
            "<url><loc>junk-text-no-scheme</loc></url>"
            "</urlset>"
        )
        with mocked_fetcher({
            "/sitemap.xml": resp(
                body, status_code=200,
                url="https://x.example/sitemap.xml",
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        # extracted_url_count includes both entries (parser kept
        # them) but only the real one shows up in_scope; junk-text
        # is neither in_scope nor out_of_scope.
        assert finding.data["extracted_url_count"] == 2
        assert finding.data["in_scope_url_count"] == 1
        assert finding.data["out_of_scope_url_count"] == 0


class SampleUrlsTests(TestCase):
    def test_sample_urls_limited(self) -> None:
        scan_run, target_run = _seed()
        # Build a urlset with many in-scope URLs to verify sample
        # truncation.
        body = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        for i in range(20):
            body += f"<url><loc>https://x.example/p{i}</loc></url>"
        body += "</urlset>"
        with mocked_fetcher({
            "/sitemap.xml": resp(
                body, status_code=200,
                url="https://x.example/sitemap.xml",
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        # MVP caps sample_urls at 10 per spec §Persistence
        # SitemapXmlFinding shape.
        assert len(finding.data["sample_urls"]) == 10


class RunnerRegistrationTests(TestCase):
    def setUp(self) -> None:
        import importlib
        from apps.stubs.sitemap_xml import runner as runner_module
        importlib.reload(runner_module)

    def test_runner_registered_under_1_12(self) -> None:
        from apps.stubs.runners import _REGISTRY
        assert "1.12" in _REGISTRY
        assert callable(_REGISTRY["1.12"])
