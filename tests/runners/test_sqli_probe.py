"""Tests for sqli_probe runner — katana artifact input, signal recording."""

from __future__ import annotations

import json
from pathlib import Path

from earn_money import config, scope
from earn_money.recon import runs
from earn_money.recon.signals import Signal
from earn_money.runners import active, sqli_probe


def _make_signal(run_id: str = "r1") -> Signal:
    return Signal(
        run_id=run_id, tool="sqli-probe", signal_type="sqli_candidate",
        asset="target.cocode.dk", target="https://target.cocode.dk/search?q=x",
        signature="sqli|error_based|q|https://target.cocode",
        payload=json.dumps({"url": "https://target.cocode.dk/search?q=x", "severity": "high"}),
        observed_at="2026-05-15T12:00:00Z",
    )


def _write_scope(paths: config.Paths) -> None:
    s = scope.Scope(
        platform="local", slug="juice-shop", policy="rate-limited-OK",
        in_scope=["target.cocode.dk"], out_of_scope=[], notes="",
        scope_hash="x", last_synced="2026-05-15T00:00:00Z",
    )
    scope.write_scope(paths.scope_file("local", "juice-shop"), s)


def _write_katana_artifact(paths: config.Paths, urls: list[str]) -> str:
    """Write a fake discovered_urls.jsonl and a recon_run row; return artifact_dir."""
    import uuid

    from earn_money import db
    from earn_money._time import now_iso

    run_id = uuid.uuid4().hex
    artifact_dir = paths.root / f"recon/outputs/local/juice-shop/katana/2026-05-15/{run_id}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"url": u, "method": "GET", "status_code": 200}) for u in urls]
    (artifact_dir / "discovered_urls.jsonl").write_text("\n".join(lines), encoding="utf-8")

    conn = db.open_db(paths.program_db("local", "juice-shop"))
    now = now_iso()
    runs.start_run(
        conn, run_id=run_id, platform="local", slug="juice-shop", tool="katana",
        started_at=now, artifact_dir=str(artifact_dir), input_count=1,
    )
    runs.finish_run(
        conn, run_id=run_id, finished_at=now_iso(), status="success",
        output_count=len(urls), signal_count=0, source_failures=0, oos_drops=0,
    )
    conn.close()
    return str(artifact_dir)


def test_sqli_probe_skips_when_no_katana_artifact(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _write_scope(paths)
    result = sqli_probe.run_program(
        paths, "local", "juice-shop",
        tool_run=lambda _: active.ToolRunResult(outputs=()),
    )
    assert result.prereq_skipped is True


def test_sqli_probe_records_signals(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _write_scope(paths)
    _write_katana_artifact(paths, ["https://target.cocode.dk/search?q=test"])

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(_make_signal(),))

    result = sqli_probe.run_program(
        paths, "local", "juice-shop", tool_run=fake_tool,
    )
    assert result.prereq_skipped is False
    assert result.outputs_recorded == 1
    assert result.targets_scanned == 1


def test_sqli_probe_drops_oos_signals(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _write_scope(paths)
    _write_katana_artifact(paths, ["https://target.cocode.dk/search?q=test"])

    oos_sig = Signal(
        run_id="r1", tool="sqli-probe", signal_type="sqli_candidate",
        asset="attacker.com", target="https://attacker.com/x?q=y",
        signature="sqli|error_based|q|x",
        payload="{}", observed_at="t",
    )

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(_make_signal(), oos_sig))

    result = sqli_probe.run_program(
        paths, "local", "juice-shop", tool_run=fake_tool,
    )
    assert result.outputs_recorded == 1
    assert result.oos_drops == 1


def test_sqli_probe_skips_urls_without_params(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _write_scope(paths)
    _write_katana_artifact(paths, [
        "https://target.cocode.dk/page",       # no params — should be filtered
        "https://target.cocode.dk/search?q=x", # has params — included
    ])
    seen: list[list[str]] = []

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        seen.append(targets)
        return active.ToolRunResult(outputs=())

    sqli_probe.run_program(
        paths, "local", "juice-shop", tool_run=fake_tool,
    )
    assert seen == [["https://target.cocode.dk/search?q=x"]]
