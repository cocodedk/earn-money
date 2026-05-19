"""Tests for stub 1.13 runner.run — fetch canonical + legacy +
classify + persist."""
from __future__ import annotations

from django.test import TestCase

from apps.evidence.models import Evidence
from apps.findings.models import Finding, FindingStatus
from apps.stubs._test_factories import seed_target_run

from ..runner import run
from ._helpers import mocked_fetcher, resp


_VALID = (
    "Contact: mailto:s@x.example\n"
    "Expires: 2030-01-01T00:00:00Z\n"
    "Canonical: https://x.example/.well-known/security.txt\n"
)


def _seed():
    return seed_target_run(stub_slug="1.13", host="x.example")


class CanonicalValidTests(TestCase):
    def test_valid_canonical_writes_present_valid_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/.well-known/security.txt": resp(
                _VALID, status_code=200,
                url="https://x.example/.well-known/security.txt",
            ),
            "/security.txt": resp("", status_code=404),
        }):
            run(scan_run, target_run)

        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.status == FindingStatus.CONFIRMED
        assert finding.confidence == "high"
        assert finding.data["finding_type"] == "security_txt_present_valid"
        assert finding.data["http_status"] == 200


class MissingTests(TestCase):
    def test_both_404_writes_missing_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({}):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["finding_type"] == "missing_security_txt"
        assert finding.confidence == "high"


class BlockedTests(TestCase):
    def test_403_on_canonical_writes_blocked_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/.well-known/security.txt": resp("denied", status_code=403),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["finding_type"] == "blocked_security_txt"


class NoContactTests(TestCase):
    def test_present_no_contact_yields_no_contact_finding(self) -> None:
        scan_run, target_run = _seed()
        body = "Expires: 2030-01-01T00:00:00Z\n"
        with mocked_fetcher({
            "/.well-known/security.txt": resp(
                body, status_code=200,
                url="https://x.example/.well-known/security.txt",
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["finding_type"] == "security_txt_no_contact"


class EvidenceTests(TestCase):
    def test_evidence_linked_to_finding(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/.well-known/security.txt": resp(
                _VALID, status_code=200,
                url="https://x.example/.well-known/security.txt",
            ),
        }):
            run(scan_run, target_run)
        evidence = Evidence.objects.filter(scan_run=scan_run).first()
        finding = Finding.objects.get(scan_run=scan_run)
        assert evidence is not None
        assert str(evidence.id) in finding.data["evidence_ids"]


class LegacyOnlyTests(TestCase):
    def test_canonical_404_legacy_200_yields_legacy_only(self) -> None:
        scan_run, target_run = _seed()
        with mocked_fetcher({
            "/.well-known/security.txt": resp("", status_code=404),
            "/security.txt": resp(
                _VALID, status_code=200,
                url="https://x.example/security.txt",
            ),
        }):
            run(scan_run, target_run)
        finding = Finding.objects.get(scan_run=scan_run)
        assert finding.data["finding_type"] == "security_txt_legacy_only"


class RunnerRegistrationTests(TestCase):
    def setUp(self) -> None:
        import importlib
        from apps.stubs.security_txt import runner as runner_module
        importlib.reload(runner_module)

    def test_runner_registered_under_1_13(self) -> None:
        from apps.stubs.runners import _REGISTRY
        assert "1.13" in _REGISTRY
        assert callable(_REGISTRY["1.13"])
