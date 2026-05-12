"""Shared helpers for triage tests."""
from __future__ import annotations

from pathlib import Path

from earn_money import config, db
from earn_money import scope as scope_mod
from earn_money.recon import runs, services, signals
from earn_money.recon.services import HttpService
from earn_money.recon.signals import Signal
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


def engine_paths(tmp_repo: Path) -> config.Paths:
    """A Paths with RECON_ENABLED touched and the example program registered."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    register_program(paths)
    return paths


def seed_nuclei_run_with_signal(paths: config.Paths) -> None:
    """Seed one untriaged nuclei run with a single template_match signal."""
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        services.upsert_service(conn, HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200,
            title="Acme API", server="nginx",
            technologies=("nginx",),
            redirect_to=None, tls_summary=None,
            observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
            in_scope_at_observation=True,
        ))
        runs.start_run(
            conn, run_id="nuclei-r1", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-12T02:15:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-r1", finished_at="2026-05-12T02:20:00Z",
            status="success", output_count=1, signal_count=1,
            source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-r1", tool="nuclei", signal_type="template_match",
            asset="api.example.com",
            target="https://api.example.com/search?q=foo",
            signature="CVE-2023-1234|primary|",
            payload='{"template_id":"CVE-2023-1234","matcher_name":"primary",'
                    '"matched_at":"https://api.example.com/search?q=foo",'
                    '"severity":"high","name":"Acme SQLi"}',
            observed_at="2026-05-12T02:16:00Z",
        )])
    finally:
        conn.close()
