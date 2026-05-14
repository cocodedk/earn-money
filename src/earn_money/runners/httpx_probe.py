"""Active HTTP probing runner — converts in-scope assets to live HTTP
service observations using the ProjectDiscovery httpx CLI.

CLI entry-point and watchdog wiring live in httpx_probe_cli.py.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from earn_money import config, db, scope
from earn_money._time import now_iso
from earn_money.recon import runs, services
from earn_money.runners import active

ToolRun = Callable[[list[str]], active.ToolRunResult]


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
    run_id: str | None = None,
    max_targets: int | None = None,
) -> active.ActiveRunResult:
    """Gate-check → load assets → scope filter → call tool → upsert services
    → write manifest → record run.  Returns a typed result for the digest.

    ``max_targets`` caps the in-scope asset set to the first N entries
    (alphabetical) so wildcard-explosion programs don't run forever.
    """
    s = active.check_gates(paths, platform, slug, mode="active")

    run_id = run_id or uuid.uuid4().hex
    now = now_iso()
    artifact_dir = paths.root / (
        f"recon/outputs/{platform}/{slug}/httpx/{now[:10]}/{run_id}"
    )

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        targets = _load_in_scope_assets(conn, s)
        if max_targets is not None and max_targets >= 0:
            targets = targets[:max_targets]
        runs.start_run(
            conn, run_id=run_id, platform=platform, slug=slug, tool="httpx",
            started_at=now, artifact_dir=str(artifact_dir), input_count=len(targets),
        )

        try:
            tool_result = (
                tool_run(targets) if targets
                else active.ToolRunResult(outputs=())
            )
        except Exception as exc:
            finished = now_iso()
            runs.finish_run(
                conn, run_id=run_id, finished_at=finished, status="failed",
                output_count=0, signal_count=0, source_failures=1, oos_drops=0,
                error_summary=f"{type(exc).__name__}: {exc}",
            )
            raise

        raw_services: tuple[services.HttpService, ...] = tuple(tool_result.outputs)
        in_scope = [
            svc for svc in raw_services
            if scope.is_in_scope(svc.subdomain, s.in_scope, s.out_of_scope)
        ]
        oos_drops = len(raw_services) - len(in_scope)

        for svc in in_scope:
            services.upsert_service(conn, svc)

        _write_manifest(artifact_dir, {
            "run_id": run_id, "tool": "httpx",
            "platform": platform, "slug": slug,
            "started_at": now, "input_count": len(targets),
            "output_count": len(in_scope), "oos_drops": oos_drops,
        })

        run_status, terminated_reason = active.resolve_run_status(tool_result)
        finished = now_iso()
        runs.finish_run(
            conn, run_id=run_id, finished_at=finished, status=run_status,
            output_count=len(in_scope), signal_count=0,
            source_failures=tool_result.source_failures, oos_drops=oos_drops,
            terminated_reason=terminated_reason,
        )
        return active.ActiveRunResult(
            run_id=run_id,
            targets_considered=len(targets),
            targets_scanned=len(targets),
            artifacts_written=1,
            outputs_recorded=len(in_scope),
            source_failures=tool_result.source_failures,
            oos_drops=oos_drops,
            terminated_reason=terminated_reason,
        )
    finally:
        conn.close()


