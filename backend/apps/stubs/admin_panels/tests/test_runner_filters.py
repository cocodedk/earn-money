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


class RedirectTests(TestCase):
    def test_302_to_same_origin_admin_path_emits_medium(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={
                "/admin": _probe("", 302, location="/admin/login"),
            },
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/admin")
        assert finding.confidence == "medium"
        assert finding.data["signal_kind"] == "redirect_to_admin"

    def test_302_to_non_admin_path_skipped(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={"/admin": _probe("", 302, location="/login")},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()

    def test_302_to_cross_origin_skipped(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={
                "/admin": _probe(
                    "", 302, location="https://other.example/admin",
                ),
            },
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()

    def test_302_without_location_header_skipped(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={"/admin": _probe("", 302, location=None)},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert not Finding.objects.filter(data__path="/admin").exists()

    def test_302_with_absolute_same_origin_admin_url_fires(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={
                "/admin": _probe(
                    "", 302, location="https://x.example/admin/login",
                ),
            },
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Finding.objects.filter(data__path="/admin").exists()


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
