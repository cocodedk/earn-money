"""Tests for stub 1.10 runner.run — integration of fetch + classify
+ persist with mocked HTTP.
"""
from __future__ import annotations

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding, FindingStatus
from apps.stubs._test_factories import seed_target_run

from ..runner import run
from ._helpers import mocked_fetcher, resp


def _seed():
    return seed_target_run(stub_slug="1.10")


class RunnerHappyPathTests(TestCase):
    def test_phpinfo_match_writes_evidence_and_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": resp("home", status_code=200),
            "/phpinfo.php": resp(
                "<title>phpinfo()</title>\n<h1>PHP Version 8.2</h1>",
                status_code=200,
                headers={"Content-Type": "text/html"},
            ),
        }):
            run(scan_run, target_run)

        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.confidence == "high"
        assert finding.data["kind"] == "phpinfo"
        assert finding.data["finding_type"] == "debug_page"
        assert finding.data["exposure"] == "public"

        evidence = Evidence.objects.get(scan_run=scan_run)
        assert evidence.url.endswith("/phpinfo.php")
        # Finding.data should link back to the Evidence id.
        assert str(evidence.id) in finding.data["evidence_ids"]


class RunnerRedactionTests(TestCase):
    def test_secret_values_redacted_in_raw_excerpt(self) -> None:
        scan_run, target_run = _seed()
        body = (
            "SECRET_KEY=super-secret-value\n"
            "DATABASE_URL=postgres://u:p4ss@db/x\n"
            "DEBUG=True"
        )
        with mocked_fetcher({
            "/": resp("home", status_code=200),
            "/actuator/env": resp(
                body,
                status_code=200,
                headers={"Content-Type": "application/json"},
            ),
        }):
            run(scan_run, target_run)

        evidence = Evidence.objects.get(scan_run=scan_run)
        assert "super-secret-value" not in evidence.raw_excerpt
        assert "p4ss" not in evidence.raw_excerpt
        assert "<REDACTED>" in evidence.raw_excerpt


class RunnerNoFindingsTests(TestCase):
    def test_target_unreachable_writes_nothing(self) -> None:
        import httpx
        scan_run, target_run = _seed()

        def raise_(_url, **_kwargs):
            raise httpx.ConnectError("baseline unreachable")

        with mocked_fetcher(get_side_effect=raise_):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0
        assert Evidence.objects.filter(scan_run=scan_run).count() == 0

    def test_all_404s_writes_nothing(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({"/": resp("home", status_code=200)}):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0

    def test_spa_fallthrough_writes_nothing(self) -> None:
        # Every seeded path returns the homepage body → generic_fallback.
        scan_run, target_run = _seed()
        homepage = "<!doctype html><body>SPA root</body>"
        with mocked_fetcher(
            get_side_effect=lambda url, **_k: resp(
                homepage, status_code=200,
                headers={"Content-Type": "text/html"},
            ),
        ):
            run(scan_run, target_run)

        assert Finding.objects.filter(scan_run=scan_run).count() == 0


class RunnerAuthBoundaryTests(TestCase):
    def test_401_on_actuator_yields_candidate_medium(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/": resp("home", status_code=200),
            "/actuator/env": resp("unauthorized", status_code=401),
        }):
            run(scan_run, target_run)

        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.confidence == "medium"
        assert finding.data["kind"] == "spring_actuator"
        assert finding.data["exposure"] == "blocked"


class RunnerRegistrationTests(TestCase):
    def test_runner_registered_under_1_10(self) -> None:
        from apps.stubs.runners import _REGISTRY
        assert "1.10" in _REGISTRY
        assert _REGISTRY["1.10"] is run


class ClassifyAllControlMarkerTests(TestCase):
    def test_control_marker_paths_skipped(self) -> None:
        # Defensive: even if a future fetcher emits control nonces,
        # the runner refuses to classify them — the marker says
        # "this is a soft-404 reference, not an endpoint hit".
        from apps.stubs.debug_pages.fetcher import CONTROL_MARKER
        from apps.stubs.debug_pages.runner import _classify_all
        probes = {
            f"/{CONTROL_MARKER}nonce_x": {
                "status": 200,
                "body": "<title>phpinfo()</title>\nPHP Version 8",
                "headers": {"content-type": "text/html"},
                "location": None,
            },
        }
        assert _classify_all(probes, baseline_body="home") == []
