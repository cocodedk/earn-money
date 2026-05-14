"""Tests for the katana_crawl runner."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from earn_money import config, db, flags, policy, scope
from earn_money._time import to_iso
from earn_money.recon import runs, services
from earn_money.recon.katana_tool import DiscoveredUrl
from earn_money.runners import active, katana_crawl


def _seed_scope(
    paths: config.Paths,
    *,
    policy_value: scope.Policy = "rate-limited-OK",
    in_scope: list[str] | None = None,
) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope or ["api.example.com"],
        out_of_scope=[],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _seed_httpx(paths: config.Paths, host: str = "api.example.com") -> None:
    now = datetime.now(UTC)
    started_at = to_iso(now - timedelta(minutes=5))
    finished_at = to_iso(now - timedelta(minutes=1))
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="httpx-r1", platform="hackerone", slug="example",
            tool="httpx", started_at=started_at,
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-r1", finished_at=finished_at,
            status="success", output_count=1,
            signal_count=0, source_failures=0, oos_drops=0,
        )
        services.upsert_service(conn, services.HttpService(
            subdomain=host, scheme="https", port=443,
            url=f"https://{host}/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ))
    finally:
        conn.close()


def _make_discovered(url: str, status: int = 200) -> DiscoveredUrl:
    return DiscoveredUrl(url=url, status_code=status, content_type="text/html", method="GET")


def test_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths)
    _seed_httpx(paths)
    with pytest.raises(flags.ReconDisabled):
        katana_crawl.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _t: active.ToolRunResult(outputs=()),
        )


def test_refuses_when_policy_manual_only(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, policy_value="manual-only")
    _seed_httpx(paths)
    with pytest.raises(policy.PolicyViolation):
        katana_crawl.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _t: active.ToolRunResult(outputs=()),
        )


def test_prereq_missing_writes_skipped_run(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)

    result = katana_crawl.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _t: active.ToolRunResult(outputs=()),
    )
    assert result.prereq_skipped is True


def test_writes_discovered_urls_artifact(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    _seed_httpx(paths)

    def fake(_t: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(
            _make_discovered("https://api.example.com/admin"),
            _make_discovered("https://api.example.com/v1/users", status=401),
            _make_discovered("https://attacker.com/payload"),
        ))

    result = katana_crawl.run_program(
        paths, "hackerone", "example", tool_run=fake,
    )
    assert result.outputs_recorded == 2
    assert result.oos_drops == 1

    jsonl_path = next(
        (paths.root / "recon/outputs/hackerone/example/katana").rglob(
            "discovered_urls.jsonl"
        )
    )
    rows = [json.loads(line) for line in jsonl_path.read_text().splitlines()]
    urls = {r["url"] for r in rows}
    assert urls == {
        "https://api.example.com/admin",
        "https://api.example.com/v1/users",
    }


def test_does_not_insert_into_signals_table(tmp_repo: Path) -> None:
    """v1: discovered URLs are file-only; signals table stays untouched."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    _seed_httpx(paths)

    katana_crawl.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _t: active.ToolRunResult(outputs=(
            _make_discovered("https://api.example.com/admin"),
        )),
    )
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT COUNT(*) FROM signals WHERE tool = 'katana'"
    ).fetchone()
    conn.close()
    assert rows[0] == 0


def test_manifest_records_roe_block(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    _seed_httpx(paths)

    katana_crawl.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _t: active.ToolRunResult(outputs=()),
    )
    manifest = json.loads(
        next(
            (paths.root / "recon/outputs/hackerone/example/katana").rglob("manifest.json")
        ).read_text(encoding="utf-8")
    )
    assert manifest["tool"] == "katana"
    assert manifest["roe"]["dos_authorized"] is False
    assert manifest["roe"]["max_requests_per_second"] == 10
