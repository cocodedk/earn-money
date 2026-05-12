"""End-to-end nuclei smoke against the mock target.

Auto-skips when:
- The nuclei binary is not on PATH at ~/go/bin/nuclei or ~/.local/bin/nuclei
- The synthetic template fixture is absent

Uses a private unsafe builder so the fixture template doesn't need to
be installed into ~/.nuclei-templates/. The production code path's
approved-list check is unaffected.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import uuid
from pathlib import Path

import pytest

from earn_money import config, db, scope
from earn_money.recon import nuclei_tool, runs, services
from earn_money.recon.services import HttpService
from earn_money.runners import active, nuclei_scan

_PD_NUCLEI = shutil.which("nuclei")
_TEMPLATE = (
    Path(__file__).parent.parent
    / "fixtures" / "nuclei_templates" / "synthetic-200.yaml"
)

pytestmark = pytest.mark.skipif(
    not _PD_NUCLEI or not _TEMPLATE.exists(),
    reason="ProjectDiscovery nuclei binary or synthetic template not present",
)


def _seed(tmp_repo: Path) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["127.0.0.1"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        services.upsert_service(conn, HttpService(
            subdomain="127.0.0.1", scheme="http", port=18081,
            url="http://127.0.0.1:18081/", status_code=200,
            title="In-Scope A", server="mock-target/1.0",
            technologies=(), redirect_to=None, tls_summary=None,
            observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
            in_scope_at_observation=True,
        ))
        runs.start_run(
            conn, run_id="httpx-r1", platform="hackerone", slug="example",
            tool="httpx", started_at="2026-05-12T01:00:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-r1", finished_at="2026-05-12T01:05:00Z",
            status="success", output_count=1, signal_count=0,
            source_failures=0, oos_drops=0,
        )
    finally:
        conn.close()
    return paths


def _make_tool_run(monkeypatch: pytest.MonkeyPatch):  # type: ignore[type-arg]
    from earn_money.runners import batch

    nuclei_path = Path(_PD_NUCLEI)  # type: ignore[arg-type]
    pd_bin_dir = str(nuclei_path.parent)
    current_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{pd_bin_dir}:{current_path}")

    def build_unsafe(chunk: list[str]) -> list[str]:
        return [
            "nuclei",
            "-u", ",".join(chunk),
            "-t", str(_TEMPLATE),
            "-jsonl", "-silent", "-no-color",
            "-disable-redirects", "-no-interactsh",
            "-disable-update-check",
        ]

    e2e_run_id = uuid.uuid4().hex

    def tool_run(targets: list[str]) -> active.ToolRunResult:
        result = batch.run_batches(
            targets,
            command_factory=build_unsafe,
            max_batch_size=50, max_batch_duration_s=60.0,
        )
        raw = "\n".join(line for b in result.batches for line in b.lines)
        return active.ToolRunResult(
            outputs=tuple(nuclei_tool.parse_jsonl(raw, run_id=e2e_run_id, observed_at="t")),
            aborted=result.aborted,
        )

    return tool_run, e2e_run_id


def test_e2e_nuclei_scan_writes_signal_against_mock_target(
    tmp_repo: Path, mock_target: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _seed(tmp_repo)
    tool_run, e2e_run_id = _make_tool_run(monkeypatch)

    result = nuclei_scan.run_program(
        paths, "hackerone", "example", tool_run=tool_run, run_id=e2e_run_id,
    )
    assert result.signals_emitted >= 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    sigs = conn.execute(
        "SELECT signal_type, asset, signature FROM signals WHERE tool = 'nuclei'"
    ).fetchall()
    runs_rows = conn.execute(
        "SELECT status FROM recon_runs WHERE tool = 'nuclei'"
    ).fetchall()
    conn.close()
    assert runs_rows == [("success",)]
    assert any("synthetic-200-title-match" in sig for _, _, sig in sigs)

    nuclei_out = (
        paths.root / "recon" / "outputs" / "hackerone" / "example" / "nuclei"
    )
    manifests = list(nuclei_out.rglob("manifest.json"))
    assert len(manifests) == 1
    sig_files = list(nuclei_out.rglob("signals.jsonl"))
    assert len(sig_files) == 1
    sig_lines = [ln for ln in sig_files[0].read_text(encoding="utf-8").splitlines() if ln]
    assert any(
        json.loads(ln)["signal_type"] == "template_match" for ln in sig_lines
    )
