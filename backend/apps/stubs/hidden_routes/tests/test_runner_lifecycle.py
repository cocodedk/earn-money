"""Dedup, skip-path and registry tests for stub 1.6 runner."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding

from ..runner import run

from ._runner_helpers import make_nonce_bundle, make_probe, seed_for_1_6


_seed = seed_for_1_6
_nonce_bundle = make_nonce_bundle
_probe = make_probe


class DedupTests(TestCase):
    def test_same_path_from_probe_and_metadata_collapses(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="404", nonce_status=404,
            probes={
                "/admin": _probe("Admin Console", 200),
                "/robots.txt": _probe("Disallow: /admin\n", 200),
            },
        )
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        admin_findings = Finding.objects.filter(data__path="/admin")
        assert admin_findings.count() == 1


class ProbeStatus404Tests(TestCase):
    def test_404_status_skips_finding(self) -> None:
        # Some servers return 404 with a body distinct from soft-404.
        # 404 means "no resource here" regardless of body shape.
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="generic 404", nonce_status=404,
            probes={"/admin": _probe("custom 404 body", 404)},
        )
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()


class NoBaselineTests(TestCase):
    def test_baseline_none_yields_no_findings(self) -> None:
        scan_run, target_run = _seed()
        bundle = {"baseline": None, "probes": {}}
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0
        assert Evidence.objects.count() == 0


class NoMatchTests(TestCase):
    def test_all_probes_match_soft_404_yields_zero(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="<html>not found</html>", nonce_status=200,
        )
        for path in ("/admin", "/login", "/api"):
            bundle["probes"][path] = _probe("<html>not found</html>", 200)
        with patch(
            "apps.stubs.hidden_routes.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.count() == 0


class RegistryDispatchTests(TestCase):
    def setUp(self) -> None:
        from apps.stubs.runners import register

        register("1.6")(run)

    def test_registered_under_1_6(self) -> None:
        from apps.stubs.runners import get as get_runner

        assert get_runner("1.6") is run
