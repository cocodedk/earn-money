"""Runner-level tests for stub 1.9 old-endpoints."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding, FindingStatus

from ..runner import run

from ._runner_helpers import make_bundle, make_probe, seed_for_1_9


class DeprecationHeaderTests(TestCase):
    """Spec §7 row 1: live response with Deprecation/Sunset/Warning:299/
    Link rel=deprecation|sunset → status=confirmed, confidence=high."""

    def test_deprecation_header_yields_confirmed_high(self) -> None:
        scan_run, target_run = seed_for_1_9()
        bundle = make_bundle(
            probes={
                "/api/v1": make_probe(
                    body="{}", status=200,
                    headers={"deprecation": "true"},
                ),
            },
        )
        with patch(
            "apps.stubs.old_endpoints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/api/v1")
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.confidence == "high"
        assert finding.data["finding_type"] == "old_endpoint"

    def test_sunset_header_yields_confirmed_high(self) -> None:
        scan_run, target_run = seed_for_1_9()
        bundle = make_bundle(
            probes={
                "/api/v1": make_probe(
                    body="{}", status=200,
                    headers={"sunset": "Wed, 31 Dec 2025 23:59:59 GMT"},
                ),
            },
        )
        with patch(
            "apps.stubs.old_endpoints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/api/v1")
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.confidence == "high"

    def test_evidence_pair_created(self) -> None:
        # Spec §Persistence: each Finding has at least one Evidence row
        # in the same transaction.
        scan_run, target_run = seed_for_1_9()
        bundle = make_bundle(
            probes={
                "/api/v1": make_probe(
                    body="{}", status=200,
                    headers={"deprecation": "true"},
                ),
            },
        )
        with patch(
            "apps.stubs.old_endpoints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        assert Evidence.objects.count() == 1
        finding = Finding.objects.get(data__path="/api/v1")
        assert finding.data["evidence_ids"]


class NoBaselineTests(TestCase):
    def test_no_baseline_yields_no_findings(self) -> None:
        scan_run, target_run = seed_for_1_9()
        bundle = {"baseline": None, "probes": {}}
        with patch(
            "apps.stubs.old_endpoints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)
        assert Finding.objects.count() == 0
        assert Evidence.objects.count() == 0


class HardNotFoundTests(TestCase):
    """Spec §Negative assertions: must not create a finding for hard
    404 or 410. The seeded /api/v1 path returning 404 produces nothing."""

    def test_404_response_skipped(self) -> None:
        scan_run, target_run = seed_for_1_9()
        bundle = make_bundle(
            probes={"/api/v1": make_probe(body="", status=404)},
        )
        with patch(
            "apps.stubs.old_endpoints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)
        assert not Finding.objects.filter(data__path="/api/v1").exists()

    def test_410_response_skipped(self) -> None:
        scan_run, target_run = seed_for_1_9()
        bundle = make_bundle(
            probes={"/api/v1": make_probe(body="", status=410)},
        )
        with patch(
            "apps.stubs.old_endpoints.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)
        assert not Finding.objects.filter(data__path="/api/v1").exists()


class RegistryDispatchTests(TestCase):
    def setUp(self) -> None:
        from apps.stubs.runners import register

        register("1.9")(run)

    def test_registered_under_1_9(self) -> None:
        from apps.stubs.runners import get as get_runner

        assert get_runner("1.9") is run
