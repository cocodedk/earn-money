"""End-to-end integration test for the httpx_probe runner.

Runs the real ProjectDiscovery httpx binary against the mock target via the
full runner code path.  Self-skips when the PD httpx binary is not installed.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from earn_money import config, db, scope
from earn_money.recon import assets, services
from earn_money.runners import httpx_probe

_PD_HTTPX = Path.home() / "go" / "bin" / "httpx"

pytestmark = pytest.mark.skipif(
    not _PD_HTTPX.exists(),
    reason="ProjectDiscovery httpx binary not found at ~/go/bin/httpx",
)


def _seed(tmp_repo: Path) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["127.0.0.1"],
        out_of_scope=[], notes="",
        scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)
    conn = db.open_db(paths.program_db("hackerone", "example"))
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="127.0.0.1", ips=("127.0.0.1",))],
        observed_at="2026-05-12T07:00:00Z", in_scope=True,
    )
    conn.close()
    return paths


def _make_tool_run(url: str, run_id: str, monkeypatch: pytest.MonkeyPatch):  # type: ignore[type-arg]
    """Return a tool_run closure that probes exactly one URL via PD httpx.

    Prepends ~/go/bin to PATH so the subprocess resolves the PD binary instead
    of the Python httpx wrapper that may sit earlier on the user's PATH.
    """
    from earn_money.recon import httpx_tool
    from earn_money.runners import batch

    pd_bin_dir = str(_PD_HTTPX.parent)
    current_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{pd_bin_dir}:{current_path}")

    def tool_run(_targets: list[str]) -> list[services.HttpService]:
        result = batch.run_batches(
            [url],
            command_factory=lambda chunk: httpx_tool.build_command(chunk),
            max_batch_size=1, max_batch_duration_s=10.0,
        )
        raw = "\n".join(line for b in result.batches for line in b.lines)
        return httpx_tool.parse_jsonl(raw, run_id=run_id, observed_at="t")

    return tool_run


def test_e2e_probes_in_scope_target(
    tmp_repo: Path, mock_target: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _seed(tmp_repo)

    tool_run = _make_tool_run(
        "http://127.0.0.1:18081/", "e2e", monkeypatch
    )
    result = httpx_probe.run_program(
        paths, "hackerone", "example", tool_run=tool_run,
    )
    assert result.targets_scanned >= 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT subdomain, status_code FROM http_services"
    ).fetchall()
    runs_rows = conn.execute(
        "SELECT status FROM recon_runs"
    ).fetchall()
    conn.close()

    assert any(r[0] == "127.0.0.1" and r[1] == 200 for r in rows)
    assert runs_rows == [("success",)]


def test_e2e_captures_redirect_without_following(
    tmp_repo: Path, mock_target: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Port 18082 serves a 301 to port 18083 (the OOS host). The real
    httpx must record the 301 + redirect_to without following — proving
    redirects are not followed by default. We then assert that no row
    exists for the OOS host (no traffic was sent to it)."""
    paths = _seed(tmp_repo)

    tool_run = _make_tool_run(
        "http://127.0.0.1:18082/", "e2e-redirect", monkeypatch
    )
    httpx_probe.run_program(
        paths, "hackerone", "example", tool_run=tool_run,
    )

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    redirect_rows = conn.execute(
        "SELECT status_code, redirect_to FROM http_services "
        "WHERE port = 18082"
    ).fetchall()
    oos_port_rows = conn.execute(
        "SELECT port FROM http_services WHERE port = 18083"
    ).fetchall()
    conn.close()

    assert redirect_rows == [(301, "http://127.0.0.1:18083/")]
    assert oos_port_rows == []
