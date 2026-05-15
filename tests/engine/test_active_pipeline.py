"""Tests for the active-pipeline orchestrator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from earn_money import config, db, scope
from earn_money._time import to_iso
from earn_money.engine import active_pipeline
from earn_money.recon import assets, runs, services
from earn_money.runners import active


def _seed_scope(paths: config.Paths) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["api.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _seed_httpx_run(paths: config.Paths) -> None:
    """Recent httpx success so nuclei/sourcemap/katana/graphql don't skip."""
    now = datetime.now(UTC)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="httpx-bootstrap", platform="hackerone", slug="example",
            tool="httpx", started_at=to_iso(now - timedelta(minutes=10)),
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-bootstrap",
            finished_at=to_iso(now - timedelta(minutes=5)),
            status="success", output_count=1, signal_count=0,
            source_failures=0, oos_drops=0,
        )
        services.upsert_service(conn, services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200,
            title=None, server=None, technologies=(),
            redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-bootstrap",
            in_scope_at_observation=True,
        ))
        assets.upsert_assets(
            conn,
            [assets.AssetObservation(subdomain="api.example.com", ips=())],
            observed_at="t", in_scope=True,
        )
        # Seed a katana run so sqli-probe and xss-probe don't skip.
        katana_artifact = paths.root / "recon/outputs/hackerone/example/katana/seed/ka1"
        katana_artifact.mkdir(parents=True, exist_ok=True)
        (katana_artifact / "discovered_urls.jsonl").write_text("", encoding="utf-8")
        runs.start_run(
            conn, run_id="ka1", platform="hackerone", slug="example",
            tool="katana", started_at=to_iso(now - timedelta(minutes=8)),
            artifact_dir=str(katana_artifact), input_count=1,
        )
        runs.finish_run(
            conn, run_id="ka1",
            finished_at=to_iso(now - timedelta(minutes=4)),
            status="success", output_count=1, signal_count=0,
            source_failures=0, oos_drops=0,
        )
    finally:
        conn.close()


def _seed_roe(paths: config.Paths) -> None:
    """Seed a roe.md with injection_testing_authorized so sqli/xss don't roe_skip."""
    roe_path = paths.roe_file("hackerone", "example")
    roe_path.parent.mkdir(parents=True, exist_ok=True)
    roe_path.write_text("---\ninjection_testing_authorized: true\n---\n", encoding="utf-8")


def _noop_factory(
    _runner: str, _paths: config.Paths, _platform: str, _slug: str, _run_id: str,
) -> active.ToolRun:  # type: ignore[name-defined]
    return lambda _t: active.ToolRunResult(outputs=())


def test_pipeline_aborts_when_recon_disabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths)
    result = active_pipeline.run_program_pipeline(
        paths, "hackerone", "example", tool_factory=_noop_factory,
    )
    assert result.aborted_reason == "kill_switch"
    assert result.steps == ()


def test_pipeline_aborts_when_program_frozen(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    paths.freeze_flag("hackerone", "example").write_text(
        "2026-05-12T00:00:00Z\nseed reason\n", encoding="utf-8",
    )
    result = active_pipeline.run_program_pipeline(
        paths, "hackerone", "example", tool_factory=_noop_factory,
    )
    assert result.aborted_reason == "frozen"


def test_pipeline_runs_all_six_steps_in_order(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    _seed_httpx_run(paths)
    _seed_roe(paths)
    result = active_pipeline.run_program_pipeline(
        paths, "hackerone", "example", tool_factory=_noop_factory,
    )
    assert result.aborted_reason is None
    runners = [s.runner for s in result.steps]
    assert runners == [
        "httpx-probe", "nuclei-scan", "takeover-validate",
        "sourcemap-scan", "katana-crawl", "graphql-probe",
        "auth-bypass-probe", "sqli-probe", "xss-probe",
    ]
    # No prereq_skipped — httpx was seeded as a recent success.
    assert all(s.status == "ok" for s in result.steps)


def test_pipeline_marks_step_skipped_when_prereq_missing(tmp_repo: Path) -> None:
    """No httpx run → nuclei/sourcemap/katana/graphql self-report
    prereq_skipped, which the orchestrator records as 'skipped'."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    # No _seed_httpx_run() — prereq-gated runners will skip.
    result = active_pipeline.run_program_pipeline(
        paths, "hackerone", "example", tool_factory=_noop_factory,
    )
    statuses = {s.runner: s.status for s in result.steps}
    # httpx + takeover have no httpx prereq → "ok"
    assert statuses["httpx-probe"] == "ok"
    assert statuses["takeover-validate"] == "ok"
    # nuclei + sourcemap + katana + graphql all gate on httpx → "skipped"
    assert statuses["nuclei-scan"] == "skipped"
    assert statuses["sourcemap-scan"] == "skipped"
    assert statuses["katana-crawl"] == "skipped"
    assert statuses["graphql-probe"] == "skipped"


