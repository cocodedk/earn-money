"""Codex P1 — path-style token redaction tests for stub 2.7.

Split from test_redaction.py once path-style coverage grew. Shared
fixtures in `_redaction_fixtures.py`.
"""
from __future__ import annotations

import pytest

from apps.findings.models import Finding
from apps.stubs._test_factories import seed_target_run
from apps.stubs.weak_reset_expiry.tests._redaction_fixtures import (
    mailbox, run_with, wire,
)


@pytest.mark.django_db
def test_slash_separator_redacted() -> None:
    """`/reset/<token>` shape."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Click https://x.example/reset/SECRET-TOKEN-XYZ"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-TOKEN-XYZ" not in f.data["body_snippet"]
    assert "<redacted>" in f.data["body_snippet"]


@pytest.mark.django_db
def test_hyphen_separator_redacted() -> None:
    """`/reset-<token>` — hyphen separator on the plain keyword.
    Codex pass-3 P1 caught the regression here."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Click https://x.example/reset-SECRET-TOKEN to confirm"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-TOKEN" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_verify_hyphen_separator_redacted() -> None:
    """`/verify-<token>` shape."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Click https://x.example/verify-UNIQUE-NONCE"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "UNIQUE-NONCE" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_verify_slash_separator_redacted() -> None:
    """`/verify/<token>` shape."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Visit https://x.example/verify/UNIQUE-NONCE to confirm."),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "UNIQUE-NONCE" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_compound_reset_password_redacted() -> None:
    """`/reset-password/<token>` shape (Express/Rails/Django style)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Click https://x.example/reset-password/SECRET-TOKEN-XYZ"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-TOKEN-XYZ" not in f.data["body_snippet"]
    assert "<redacted>" in f.data["body_snippet"]


@pytest.mark.django_db
def test_reversed_password_reset_redacted() -> None:
    """`/password-reset/<token>` shape."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Click https://x.example/password-reset/SECRET-XYZ"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-XYZ" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_forgot_password_redacted() -> None:
    """`/forgot-password/<token>` shape."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Click https://x.example/forgot-password/SECRET-XYZ"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-XYZ" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_hyphenated_token_consumed_in_full_slash_separator() -> None:
    """`/reset/SECRET-TOKEN-XYZ` — the hyphens are part of the
    token, not separators. The regex must consume the ENTIRE
    `SECRET-TOKEN-XYZ` segment (codex pass-4 P1)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Click https://x.example/reset/SECRET-TOKEN-XYZ now"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "SECRET-TOKEN-XYZ" not in f.data["body_snippet"]
    assert "TOKEN-XYZ" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_hyphenated_token_consumed_in_full_hyphen_separator() -> None:
    """`/reset-SECRET-TOKEN-XYZ` — keyword + hyphen separator + a
    hyphenated token (codex pass-4 P1)."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Click https://x.example/reset-SECRET-TOKEN-XYZ now"),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "TOKEN-XYZ" not in f.data["body_snippet"]


@pytest.mark.django_db
def test_non_token_url_preserved() -> None:
    """A non-token URL stays intact in the snippet."""
    scan_run, target_run = seed_target_run(host="x.example", stub_slug="2.7")
    run_with(scan_run, target_run, wire(
        mailbox("Visit https://x.example/home for more info."),
    ))
    f = Finding.objects.get(scan_run=scan_run)
    assert "https://x.example/home" in f.data["body_snippet"]
