"""Positive-signal tests for stub 1.8 runner — auth-gates, body
markers, and distinct-body detection paths."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.findings.models import Finding, FindingStatus, Severity

from ..runner import run

from ._runner_helpers import make_nonce_bundle, make_probe, seed_for_1_8


_seed = seed_for_1_8
_nonce_bundle = make_nonce_bundle
_probe = make_probe


class AuthGateDetectionTests(TestCase):
    def test_401_emits_high_confidence_finding(self) -> None:
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
        assert finding.confidence == "high"
        assert finding.data["signal_kind"] == "auth_required"
        assert finding.severity == Severity.INFO
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.data["source"] == "admin_panels"

    def test_403_emits_high_confidence_finding(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={"/wp-admin/": _probe("forbidden", 403)},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/wp-admin/")
        assert finding.confidence == "high"
        assert finding.data["signal_kind"] == "auth_required"


class BodyMarkerDetectionTests(TestCase):
    def test_login_form_marker_emits_high(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={
                "/admin/login": _probe(
                    '<form><input type="password" name="pw"></form>',
                ),
            },
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/admin/login")
        assert finding.confidence == "high"
        assert finding.data["signal_kind"] == "body_markers"

    def test_admin_panel_marker_emits_high(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            probes={"/dashboard": _probe("<h1>Admin Dashboard</h1>")},
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/dashboard")
        assert finding.data["signal_kind"] == "body_markers"


class DistinctBodyTests(TestCase):
    def test_200_distinct_no_markers_emits_medium(self) -> None:
        scan_run, target_run = _seed()
        bundle = _nonce_bundle(
            nonce_body="generic 404 page", nonce_status=404,
            probes={
                "/console": _probe(
                    "Welcome to the system; please check back later.",
                ),
            },
        )
        with patch(
            "apps.stubs.admin_panels.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/console")
        assert finding.confidence == "medium"
        assert finding.data["signal_kind"] == "distinct_body"
