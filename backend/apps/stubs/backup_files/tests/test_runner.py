"""Runner tests for stub 1.7 backup-files (mocked fetcher)."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.evidence.models import Evidence, EvidenceSource
from apps.findings.models import Finding, FindingStatus, Severity
from apps.scans.models import ScanRun, ScanTargetRun
from apps.stubs._test_factories import seed_target_run

from ..runner import run


def _seed() -> tuple[ScanRun, ScanTargetRun]:
    return seed_target_run(stub_slug="1.7", host="x.example")


def _bundle(responses: dict[str, dict] | None = None) -> dict:
    return {"responses": responses or {}}


def _response(
    source_kind: str = "archive",
    body: str = "binary",
    status: int = 200,
    content_type: str = "application/zip",
) -> dict:
    return {
        "status": status,
        "content_type": content_type,
        "body": body,
        "source_kind": source_kind,
    }


class ArchiveLeakTests(TestCase):
    def test_emits_finding_for_reachable_archive(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({"/backup.zip": _response("archive")})
        with patch(
            "apps.stubs.backup_files.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/backup.zip")
        assert finding.confidence == "high"
        assert finding.severity == Severity.INFO
        assert finding.status == FindingStatus.CANDIDATE
        assert finding.data["source_kind"] == "archive"
        assert finding.data["source"] == "backup_files"

        evidence = Evidence.objects.get()
        assert evidence.source == EvidenceSource.PATH
        assert evidence.field == "archive"


class SecretFileLeakTests(TestCase):
    def test_emits_finding_for_dotenv(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/.env": _response(
                "secret_file", body="DATABASE_URL=postgres://x",
                content_type="text/plain",
            ),
        })
        with patch(
            "apps.stubs.backup_files.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        finding = Finding.objects.get(data__path="/.env")
        assert finding.data["source_kind"] == "secret_file"


class MultipleLeaksTests(TestCase):
    def test_one_finding_per_path(self) -> None:
        scan_run, target_run = _seed()
        bundle = _bundle({
            "/backup.zip": _response("archive"),
            "/.env": _response(
                "secret_file", body="x=y", content_type="text/plain",
            ),
            "/database.sql": _response(
                "db_dump", body="-- dump", content_type="application/sql",
            ),
        })
        with patch(
            "apps.stubs.backup_files.runner.fetch_evidence",
            return_value=bundle,
        ):
            run(scan_run, target_run)

        paths = {f.data["path"] for f in Finding.objects.all()}
        assert paths == {"/backup.zip", "/.env", "/database.sql"}


class NoMatchTests(TestCase):
    def test_empty_responses_yields_no_findings(self) -> None:
        scan_run, target_run = _seed()
        with patch(
            "apps.stubs.backup_files.runner.fetch_evidence",
            return_value=_bundle(),
        ):
            run(scan_run, target_run)
        assert Finding.objects.count() == 0
        assert Evidence.objects.count() == 0


class RegistryDispatchTests(TestCase):
    def setUp(self) -> None:
        from apps.stubs.runners import register

        register("1.7")(run)

    def test_registered_under_1_7(self) -> None:
        from apps.stubs.runners import get as get_runner

        assert get_runner("1.7") is run
