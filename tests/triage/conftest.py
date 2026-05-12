"""Shared helpers for triage tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import config
from earn_money.triage import findings, history


def make_finding(**overrides: object) -> findings.Finding:
    """Build a Finding with sensible defaults. Override any field via kwargs."""
    base: dict[str, object] = dict(
        finding_hash="h1",
        platform="hackerone", slug="example", vuln_class="cve-2023-1234",
        asset="api.example.com", target="https://api.example.com/",
        signature="cve-2023-1234|primary|",
        title="CVE-2023-1234 hit on api.example.com",
        severity_hint="medium", confidence=70,
        source_tool="nuclei", source_run_id="r1",
        evidence_path="recon/outputs/.../raw.jsonl",
        notes_path="findings/_queue/h1.md",
        first_seen="2026-05-12T05:00:00Z",
        last_seen="2026-05-12T05:00:00Z",
        occurrence_count=1,
        current_state="queued",
        state_changed_at="2026-05-12T05:00:00Z",
        external_report_id=None,
        payout_amount=None,
        payout_currency=None,
    )
    base.update(overrides)
    return findings.Finding(**base)  # type: ignore[arg-type]


def seed_queued(conn: object) -> None:
    """Insert one queued Finding into conn."""
    findings.upsert_finding(conn, make_finding())  # type: ignore[arg-type]


def seed_verified(conn: object) -> None:
    """Insert a queued Finding then transition to verified."""
    findings.upsert_finding(conn, make_finding())  # type: ignore[arg-type]
    history.transition_state(
        conn,  # type: ignore[arg-type]
        finding_hash="h1",
        to_state="verified",
        actor="operator",
        note=None,
        now="2026-05-12T06:00:00Z",
    )


def register_program(
    paths: config.Paths,
    platform: str = "hackerone",
    slug: str = "example",
) -> None:
    """Write a minimal scope.md so the program is considered registered."""
    from earn_money import scope as scope_mod

    scope = scope_mod.Scope(
        platform=platform,
        slug=slug,
        policy="rate-limited-OK",
        in_scope=["*.example.com"],
        out_of_scope=[],
        notes="",
        scope_hash="seed",
        last_synced="2026-05-12T00:00:00Z",
    )
    scope_mod.write_scope(paths.scope_file(platform, slug), scope)


@pytest.fixture
def program_paths(tmp_repo: Path) -> config.Paths:
    """A configured Paths with a registered hackerone/example program
    (scope.md present, ready for draft_for/submit calls)."""
    paths = config.Paths.from_root(tmp_repo)
    register_program(paths)
    return paths
