"""Codex P1 — query-string token redaction tests for stub 2.7.

`?token=...`, `?code=...`, etc. Path-style cases live in
`test_redaction_path.py`. Shared fixtures in `_redaction_fixtures.py`.
"""
from __future__ import annotations

import pytest

from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run
from apps.stubs.weak_reset_expiry.tests._redaction_fixtures import (
    mailbox, run_with, wire,
)


@pytest.mark.django_db
def test_query_token_redacted() -> None:
    """Query-string `?token=<value>` → `?token=<redacted>`."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Click https://x.example/reset?token=SECRET-XYZ"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-XYZ" not in f.data["body_snippet"]
    assert "<redacted>" in f.data["body_snippet"]


@pytest.mark.django_db
def test_query_code_param_redacted() -> None:
    """Alternative query-param name `code` is also redacted."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Click https://x.example/reset?code=SECRET-CODE"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-CODE" not in f.data["body_snippet"]
