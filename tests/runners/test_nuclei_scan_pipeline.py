"""Happy-path, scope-filter, and OOS-drop tests for the nuclei-scan runner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import config, db, scope
from earn_money.recon import services, signals
from earn_money.runners import active, nuclei_scan


def _seed_scope(
    paths: config.Paths,
    *,
    policy_value: scope.Policy = "rate-limited-OK",
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope or ["*.example.com"],
        out_of_scope=out_of_scope or [],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _seed_httpx_run_and_services(
    paths: config.Paths, *, services_to_insert: list[services.HttpService]
) -> None:
    """Seed a fresh successful httpx run + matching http_services rows so
    nuclei can see a recent prereq."""
    from earn_money.recon import runs
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="httpx-r1", platform="hackerone", slug="example",
            tool="httpx", started_at="2026-05-12T01:00:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-r1", finished_at="2026-05-12T01:05:00Z",
            status="success", output_count=len(services_to_insert),
            signal_count=0, source_failures=0, oos_drops=0,
        )
        for svc in services_to_insert:
            services.upsert_service(conn, svc)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Happy-path test — asserts all 5 artifact files
# ---------------------------------------------------------------------------

def test_writes_signals_for_in_scope_services(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])

    _seed_httpx_run_and_services(
        paths, services_to_insert=[
            services.HttpService(
                subdomain="api.example.com", scheme="https", port=443,
                url="https://api.example.com/", status_code=200, title=None,
                server=None, technologies=(), redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
            ),
        ],
    )

    captured_targets: list[list[str]] = []

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        captured_targets.append(list(targets))
        return active.ToolRunResult(outputs=[
            signals.Signal(
                run_id="r", tool="nuclei", signal_type="template_match",
                asset="api.example.com",
                target="https://api.example.com/search?q=foo",
                signature="CVE-2023-1234|primary|",
                payload='{"template_id":"CVE-2023-1234"}',
                observed_at="2026-05-12T02:16:00Z",
            ),
        ])

    result = nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=fake_tool,
        run_id="nuclei-r1",
    )
    assert result.outputs_recorded == 1
    assert result.oos_drops == 0
    assert captured_targets == [["https://api.example.com/"]]

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    sigs = conn.execute(
        "SELECT signal_type, asset, signature FROM signals "
        "WHERE tool = 'nuclei'"
    ).fetchall()
    runs_rows = conn.execute(
        "SELECT status FROM recon_runs WHERE tool = 'nuclei'"
    ).fetchall()
    conn.close()
    assert sigs == [("template_match", "api.example.com", "CVE-2023-1234|primary|")]
    assert runs_rows == [("success",)]

    # All 5 required artifact files exist.
    nuclei_out = (
        paths.root / "recon" / "outputs" / "hackerone" / "example" / "nuclei"
    )
    assert len(list(nuclei_out.rglob("manifest.json"))) == 1
    assert len(list(nuclei_out.rglob("signals.jsonl"))) == 1
    assert len(list(nuclei_out.rglob("input.txt"))) == 1
    assert len(list(nuclei_out.rglob("raw.jsonl"))) == 1
    assert len(list(nuclei_out.rglob("stderr.txt"))) == 1


# ---------------------------------------------------------------------------
# OOS drop tests
# ---------------------------------------------------------------------------
def test_drops_oos_signals_from_tool_output(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def leaky_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=[
            signals.Signal(
                run_id="r", tool="nuclei", signal_type="template_match",
                asset="api.example.com", target="https://api.example.com/",
                signature="ok-sig", payload="{}", observed_at="t",
            ),
            signals.Signal(
                run_id="r", tool="nuclei", signal_type="template_match",
                asset="evil.example.com", target="https://evil.example.com/",
                signature="evil-sig", payload="{}", observed_at="t",
            ),
        ])

    result = nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=leaky_tool,
    )
    assert result.outputs_recorded == 1
    assert result.oos_drops == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT asset FROM signals WHERE tool = 'nuclei'"
    ).fetchall()
    conn.close()
    assert rows == [("api.example.com",)]


def test_drops_signals_with_oos_target_even_if_asset_in_scope(
    tmp_repo: Path,
) -> None:
    """B1/B5: a signal whose sig.asset is in-scope but sig.target resolves
    to an OOS hostname must be dropped and counted as oos_drops."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def leaky_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=[
            signals.Signal(
                run_id="r", tool="nuclei", signal_type="template_match",
                asset="api.example.com",          # in-scope asset
                target="https://evil.example.com/leaked",  # OOS target URL!
                signature="cve-2020-1234|matcher|",
                payload="{}", observed_at="t",
            ),
        ])

    result = nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=leaky_tool,
    )
    assert result.oos_drops == 1
    assert result.outputs_recorded == 0

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT COUNT(*) FROM signals").fetchone()
    conn.close()
    assert rows == (0,)
