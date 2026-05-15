"""XSS probe runner.

Reads discovered URLs from the latest katana artifact, filters those with
GET parameters, injects a non-executing marker per parameter, and records
`xss_candidate` signals where the marker is reflected.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from earn_money import config, db, roe, scope
from earn_money._time import now_iso, to_iso
from earn_money.recon import runs, signals
from earn_money.recon.signals import Signal
from earn_money.runners import active, nuclei_artifacts
from earn_money.runners._prereq import record_prereq_missing

ToolRun = Callable[[list[str]], active.ToolRunResult]

_PREREQ_FRESHNESS_HOURS = 24


def _recent_katana_artifact(
    conn: sqlite3.Connection, *, platform: str, slug: str, now: datetime,
) -> str | None:
    cutoff = to_iso(now - timedelta(hours=_PREREQ_FRESHNESS_HOURS))
    row = conn.execute(
        "SELECT artifact_dir FROM recon_runs WHERE platform = ? AND slug = ? "
        "AND tool = 'katana' AND status IN ('success', 'partial') "
        "AND output_count > 0 "
        "AND finished_at IS NOT NULL AND finished_at >= ? "
        "ORDER BY finished_at DESC LIMIT 1",
        (platform, slug, cutoff),
    ).fetchone()
    return row[0] if row else None


def _load_discovered_urls(artifact_dir: str) -> list[str]:
    path = Path(artifact_dir) / "discovered_urls.jsonl"
    if not path.exists():
        return []
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        url = data.get("url", "")
        method = data.get("method", "GET")
        if isinstance(url, str) and url and method == "GET" and "?" in url:
            urls.append(url)
    return urls


def run_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    tool_run: ToolRun,
    run_id: str | None = None,
    max_targets: int | None = None,
) -> active.ActiveRunResult:
    """Gate → prereq (katana artifact) → load URLs → probe → record."""
    s = active.check_gates(paths, platform, slug, mode="active")
    program_roe = roe.read_roe(paths.roe_file(platform, slug))

    run_id = run_id or uuid.uuid4().hex
    now_dt = datetime.now(UTC)
    now = to_iso(now_dt)
    artifact_dir = paths.root / (
        f"recon/outputs/{platform}/{slug}/xss/{now[:10]}/{run_id}"
    )

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        katana_artifact = _recent_katana_artifact(
            conn, platform=platform, slug=slug, now=now_dt,
        )
        if katana_artifact is None:
            return record_prereq_missing(
                conn, paths=paths, platform=platform, slug=slug,
                run_id=run_id, now=now, artifact_dir=artifact_dir, tool="xss",
                write_required_artifacts=nuclei_artifacts.write_required_artifacts,
                write_signals_jsonl=nuclei_artifacts.write_signals_jsonl,
                write_manifest=nuclei_artifacts.write_manifest,
                prereq_freshness_hours=_PREREQ_FRESHNESS_HOURS,
            )

        targets = _load_discovered_urls(katana_artifact)
        targets = [
            u for u in targets
            if scope.is_in_scope(urlparse(u).hostname or "", s.in_scope, s.out_of_scope)
        ]
        if max_targets is not None and max_targets >= 0:
            targets = targets[:max_targets]

        runs.start_run(
            conn, run_id=run_id, platform=platform, slug=slug, tool="xss",
            started_at=now, artifact_dir=str(artifact_dir),
            input_count=len(targets),
        )

        try:
            tool_result = (
                tool_run(targets) if targets else active.ToolRunResult(outputs=())
            )
        except Exception as exc:
            runs.finish_run(
                conn, run_id=run_id, finished_at=now_iso(), status="failed",
                output_count=0, signal_count=0, source_failures=1, oos_drops=0,
                error_summary=f"{type(exc).__name__}: {exc}",
            )
            raise

        found: list[Signal] = [
            o for o in tool_result.outputs if isinstance(o, Signal)
        ]
        in_scope_found = [
            sig for sig in found
            if scope.is_in_scope(sig.asset, s.in_scope, s.out_of_scope)
        ]
        oos_drops = len(found) - len(in_scope_found)

        signals.insert_signals(conn, in_scope_found)
        nuclei_artifacts.write_signals_jsonl(artifact_dir, in_scope_found)
        nuclei_artifacts.write_required_artifacts(
            artifact_dir, targets=targets,
            raw_stdout=tool_result.raw_stdout, raw_stderr=tool_result.raw_stderr,
        )
        nuclei_artifacts.write_manifest(artifact_dir, {
            "run_id": run_id, "tool": "xss",
            "platform": platform, "slug": slug,
            "started_at": now, "input_count": len(targets),
            "signal_count": len(in_scope_found), "oos_drops": oos_drops,
            "roe": program_roe.manifest_payload(),
        })

        run_status, terminated_reason = active.resolve_run_status(tool_result)
        finished = now_iso()
        runs.finish_run(
            conn, run_id=run_id, finished_at=finished, status=run_status,
            output_count=len(in_scope_found), signal_count=len(in_scope_found),
            source_failures=tool_result.source_failures, oos_drops=oos_drops,
            terminated_reason=terminated_reason,
        )
        return active.ActiveRunResult(
            run_id=run_id,
            targets_considered=len(targets),
            targets_scanned=len(targets),
            artifacts_written=1,
            outputs_recorded=len(in_scope_found),
            source_failures=tool_result.source_failures,
            oos_drops=oos_drops,
            terminated_reason=terminated_reason,
        )
    finally:
        conn.close()
