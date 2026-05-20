"""Filter-path tests for stub 1.8 runner — soft-404, redirect rules,
404/500 skip, baseline-none short-circuit, registry dispatch."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding

from ..runner import run

from ._runner_helpers import make_nonce_bundle, make_probe, seed_for_1_8


_seed = seed_for_1_8
_nonce_bundle = make_nonce_bundle
_probe = make_probe


class Soft404BothNoncesTests(TestCase):
    """Spec §Soft-404: a status-200 candidate is soft-404 only when
    its body matches BOTH random missing paths. If the two nonces
    return DIFFERENT bodies, no reliable baseline exists — no
    candidate should be suppressed by an unstable profile."""

    def test_distinct_nonce_bodies_disable_soft_404_filter(self) -> None:
        scan_run, target_run = _seed()
        bundle = {
            "baseline": {
                "status": 200, "body": "home", "url": "x", "location": None,
            },
            "probes": {
                "/scanner-baseline-aaaaaaaa": _probe("404 v1", 200),
                "/scanner-baseline-bbbbbbbb": _probe("404 v2", 200),
                # Candidate matches ONE nonce but not the other. With
                # the BOTH-required spec, this should NOT be filtered.
                "/admin": _probe("404 v1", 200),
            },
        }
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        # /admin is emitted (medium / distinct_body): baseline was
        # unreliable, so /admin reports on the merits of being a
        # non-404 status-200 distinct from the home baseline.
        finding = Finding.objects.get(data__path="/admin")
        assert finding.confidence == "medium"


class FindingTypeTests(TestCase):
    """Spec §Persistence requires
    `finding_type = "exposed_admin_panel"`."""

    def test_finding_carries_exposed_admin_panel_type(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={"/admin": _probe("unauthorized", 401)},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/admin")
        assert finding.data["finding_type"] == "exposed_admin_panel"


class Soft404SuppressTests(TestCase):
    def test_200_matching_soft_404_no_markers_suppressed(self) -> None:
        scan_run, target_run = _seed()
        shell = "<html>404 not found</html>"
        bundle = _nonce_bundle(
            nonce_body=shell, nonce_status=200,
            probes={"/admin": _probe(shell, 200)},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()

    def test_soft_404_with_markers_still_fires(self) -> None:
        # The body markers are evidence in their own right — even on a
        # soft-404-matching body, a password form is a finding.
        scan_run, target_run = _seed()
        body = '<form><input type="password" name="pw"></form>'
        bundle = _nonce_bundle(
            nonce_body=body, nonce_status=200,
            probes={"/admin": _probe(body, 200)},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/admin")
        assert finding.confidence == "high"


class SkipPathsTests(TestCase):
    def test_404_status_skipped(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={"/admin": _probe("not found", 404)},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()

    def test_500_status_skipped(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={"/admin": _probe("server error", 500)},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()

    def test_no_baseline_yields_no_findings(self) -> None:
        scan_run, target_run = _seed()
        bundle = {"baseline": None, "probes": {}}
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0
        assert Evidence.objects.count() == 0

    def test_all_paths_soft_404_yields_zero(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="<html>not found</html>", nonce_status=200,
            probes={"/admin": _probe("<html>not found</html>", 200)},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)
        assert Finding.objects.count() == 0


class RegistryDispatchTests(TestCase):
    def setUp(self) -> None:
        from apps.stubs.runners import register

        register("1.8")(run)

    def test_registered_under_1_8(self) -> None:
        from apps.stubs.runners import get as get_runner

        assert get_runner("1.8") is run
