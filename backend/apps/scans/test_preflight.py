"""API-level pre-flight tests for ScanRunSerializer.validate.

Slice D of the scope-enforcement plan: the API must refuse with an
explicit 4xx (and persist nothing) when the host's program is out-of-
scope / manual-only / ambiguous / frozen, or when RECON_ENABLED is
absent.

The autouse `_scope_enforcement_test_defaults` fixture in
`backend/conftest.py` sets up an in-scope default; these tests
override individual aspects of that default to exercise each refusal
path.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.projects.models import Project
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget


_API = "scanrun-list"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def project_and_target(db) -> tuple[Project, ScanTarget]:
    project = Project.objects.create(name="preflight-tests")
    target = ScanTarget.objects.create(
        project=project,
        base_url="https://www.algolia.com",
        host="www.algolia.com",
        status="active",
    )
    return project, target


def _payload(project: Project, target: ScanTarget) -> dict:
    return {
        "project": str(project.id),
        "stub_slug": "1.1",
        "target_ids": [str(target.id)],
    }


def test_refuses_out_of_scope_target(
    api_client: APIClient, project_and_target: tuple[Project, ScanTarget],
) -> None:
    """algolia is NOT in the default test scope (`*.cocode.dk` etc.),
    so the request must be refused 4xx and persist nothing."""
    project, target = project_and_target
    response = api_client.post(reverse(_API), _payload(project, target), format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "OutOfScope" in response.json()["target_ids"][0]
    assert ScanRun.objects.count() == 0
    assert ScanTargetRun.objects.count() == 0


def test_refuses_when_recon_enabled_missing(
    api_client: APIClient, tmp_path: Path, project_and_target: tuple[Project, ScanTarget],
) -> None:
    project, target = project_and_target
    # Override the conftest's flag path to a missing file.
    with override_settings(RECON_ENABLED_PATH=tmp_path / "no-flag"):
        response = api_client.post(reverse(_API), _payload(project, target), format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ReconDisabled" in response.json()["target_ids"][0]
    assert ScanRun.objects.count() == 0


def test_refuses_manual_only_program(api_client: APIClient, db, tmp_path: Path) -> None:
    # Build a manual-only program covering manual.example.com
    progs_root = tmp_path / "programs"
    (progs_root / "tests" / "manual").mkdir(parents=True)
    (progs_root / "tests" / "manual" / "scope.md").write_text(
        """---
platform: tests
slug: manual
policy: manual-only
in_scope:
- "manual.example.com"
out_of_scope: []
---
""", encoding="utf-8")
    (progs_root / "tests" / "manual" / "roe.md").write_text(
        "---\nmax_requests_per_second: 1\n---\n", encoding="utf-8",
    )
    flag = tmp_path / "RECON_ENABLED"
    flag.write_text("on", encoding="utf-8")

    project = Project.objects.create(name="manual-prog")
    target = ScanTarget.objects.create(
        project=project, base_url="https://manual.example.com",
        host="manual.example.com", status="active",
    )

    from apps.programs import loader
    loader._default_registry = None
    with override_settings(PROGRAMS_ROOT=progs_root, RECON_ENABLED_PATH=flag):
        response = api_client.post(reverse(_API), _payload(project, target), format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ManualOnly" in response.json()["target_ids"][0]
    assert ScanRun.objects.count() == 0


def test_refuses_frozen_program(api_client: APIClient, db, tmp_path: Path) -> None:
    progs_root = tmp_path / "programs"
    (progs_root / "tests" / "frozen").mkdir(parents=True)
    (progs_root / "tests" / "frozen" / "scope.md").write_text(
        """---
platform: tests
slug: frozen
policy: rate-limited-OK
in_scope:
- "frozen.example.com"
out_of_scope: []
---
""", encoding="utf-8")
    (progs_root / "tests" / "frozen" / "roe.md").write_text(
        "---\nmax_requests_per_second: 1\n---\n", encoding="utf-8",
    )
    # Drop a FROZEN flag.
    (progs_root / "tests" / "frozen" / "FROZEN").write_text(
        "destructive scope diff", encoding="utf-8",
    )
    flag = tmp_path / "RECON_ENABLED"
    flag.write_text("on", encoding="utf-8")

    project = Project.objects.create(name="frozen-prog")
    target = ScanTarget.objects.create(
        project=project, base_url="https://frozen.example.com",
        host="frozen.example.com", status="active",
    )

    from apps.programs import loader
    loader._default_registry = None
    with override_settings(PROGRAMS_ROOT=progs_root, RECON_ENABLED_PATH=flag):
        response = api_client.post(reverse(_API), _payload(project, target), format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ProgramFrozen" in response.json()["target_ids"][0]
    assert ScanRun.objects.count() == 0


def test_accepts_in_scope_target(api_client: APIClient, db) -> None:
    """The conftest default program covers `*.cocode.dk`; an in-scope
    target succeeds with 201."""
    project = Project.objects.create(name="happy-path")
    target = ScanTarget.objects.create(
        project=project, base_url="https://dvwa.cocode.dk",
        host="dvwa.cocode.dk", status="active",
    )
    response = api_client.post(reverse(_API), _payload(project, target), format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert ScanRun.objects.count() == 1
