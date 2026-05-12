"""Active HTTP probing runner — converts in-scope assets to live HTTP
service observations using the ProjectDiscovery httpx CLI."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from earn_money import config, db, flags, policy, scope
from earn_money.recon import runs, services
from earn_money.recon.services import HttpService
from earn_money.runners import active

ToolRun = Callable[[list[str]], list[HttpService]]


def _load_in_scope_assets(conn: sqlite3.Connection, s: scope.Scope) -> list[str]:
    cursor = conn.execute(
        "SELECT subdomain FROM assets WHERE in_scope_at_observation = 1 "
        "ORDER BY subdomain"
    )
    return [
        row[0] for row in cursor
        if scope.is_in_scope(row[0], s.in_scope, s.out_of_scope)
    ]


def _write_manifest(artifact_dir: Path, payload: dict[str, Any]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def run_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    tool_run: ToolRun,
) -> active.ActiveRunResult:
    """Gate-check → load assets → scope filter → call tool → upsert services
    → write manifest → record run.  Returns a typed result for the digest."""
    s = active.check_gates(paths, platform, slug, mode="active")

    run_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat(timespec="seconds")
    artifact_dir = paths.root / (
        f"recon/outputs/{platform}/{slug}/httpx/{now[:10]}/{run_id}"
    )

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        targets = _load_in_scope_assets(conn, s)
        runs.start_run(
            conn, run_id=run_id, platform=platform, slug=slug, tool="httpx",
            started_at=now, artifact_dir=str(artifact_dir), input_count=len(targets),
        )
        raw_services = tool_run(targets) if targets else []

        in_scope = [
            svc for svc in raw_services
            if scope.is_in_scope(svc.subdomain, s.in_scope, s.out_of_scope)
        ]
        oos_drops = len(raw_services) - len(in_scope)

        for svc in in_scope:
            services.upsert_service(
                conn, replace(svc, last_run_id=run_id, observed_at=now)
            )

        _write_manifest(artifact_dir, {
            "run_id": run_id, "tool": "httpx",
            "platform": platform, "slug": slug,
            "started_at": now, "input_count": len(targets),
            "output_count": len(in_scope), "oos_drops": oos_drops,
        })

        finished = datetime.now(UTC).isoformat(timespec="seconds")
        runs.finish_run(
            conn, run_id=run_id, finished_at=finished, status="success",
            output_count=len(in_scope), signal_count=0,
            source_failures=0, oos_drops=oos_drops,
        )
        return active.ActiveRunResult(
            run_id=run_id,
            targets_considered=len(targets),
            targets_scanned=len(targets),
            artifacts_written=1,
            signals_emitted=0,
            source_failures=0,
            oos_drops=oos_drops,
        )
    finally:
        conn.close()


def _build_real_tool(paths: config.Paths, platform: str, slug: str) -> ToolRun:
    """Wire the kill-switch watchdog + batch runner + httpx tool parser."""
    import threading

    from earn_money.recon import httpx_tool
    from earn_money.runners import batch, watchdog

    def real_tool(targets: list[str]) -> list[HttpService]:
        abort = threading.Event()
        wd = watchdog.KillSwitchWatchdog(
            paths, platform=platform, slug=slug,
            on_state_change=lambda _reason: abort.set(),
            poll_interval_s=5.0,
        )
        wd.start()
        try:
            result = batch.run_batches(
                targets,
                command_factory=lambda chunk: httpx_tool.build_command(chunk),
                max_batch_size=50, max_batch_duration_s=300.0,
                abort=abort,
            )
        finally:
            wd.stop()
        raw = "\n".join(line for b in result.batches for line in b.lines)
        now = datetime.now(UTC).isoformat(timespec="seconds")
        return httpx_tool.parse_jsonl(raw, run_id="pending", observed_at=now)

    return real_tool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="httpx-probe")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    real_tool = _build_real_tool(paths, platform=args.platform, slug=args.program)

    try:
        result = run_program(
            paths, args.platform, args.program, tool_run=real_tool,
        )
    except flags.ReconDisabled as e:
        print(f"httpx-probe: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"httpx-probe: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"httpx-probe: {e}", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"httpx-probe: unexpected error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(
        f"httpx-probe: scanned={result.targets_scanned} "
        f"services={result.targets_scanned - result.oos_drops} "
        f"oos_drops={result.oos_drops} "
        f"source_failures={result.source_failures}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
