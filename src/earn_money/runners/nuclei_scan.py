"""Template-based vulnerability scan runner.

Reads targets from `http_services`, writes `Signal` rows, re-checks every
emitted signal against program scope (oos_drops counts the rejects).

Refuses to scan without a recent httpx run (prereq freshness check); the
refusal is auditable via a `prereq_missing` Signal and a `skipped` run row.

CLI entry-point and real-tool wiring live in nuclei_scan_cli.py.
Prereq-missing audit helper lives in runners/_prereq.py.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from earn_money import config, db, scope
from earn_money._time import now_iso, to_iso
from earn_money.recon import runs, signals
from earn_money.recon.nuclei_tool import APPROVED_TEMPLATE_DIRS
from earn_money.recon.signals import Signal
from earn_money.recon.urls import target_host
from earn_money.runners import active
from earn_money.runners._prereq import record_prereq_missing

ToolRun = Callable[[list[str]], active.ToolRunResult]

_PREREQ_FRESHNESS_HOURS = 24


def _load_in_scope_service_urls(
    conn: sqlite3.Connection, s: scope.Scope
) -> list[str]:
    cursor = conn.execute(
        "SELECT url, subdomain FROM http_services "
        "WHERE in_scope_at_observation = 1 ORDER BY subdomain, scheme, port"
    )
    return [
        url for url, subdomain in cursor
        if scope.is_in_scope(subdomain, s.in_scope, s.out_of_scope)
    ]


def _recent_httpx_success(
    conn: sqlite3.Connection, *, platform: str, slug: str, now: datetime,
) -> bool:
    cutoff = to_iso(now - timedelta(hours=_PREREQ_FRESHNESS_HOURS))
    row = conn.execute(
        "SELECT 1 FROM recon_runs WHERE platform = ? AND slug = ? "
        "AND tool = 'httpx' AND status IN ('success', 'partial') "
        "AND output_count > 0 "
        "AND finished_at IS NOT NULL AND finished_at >= ? LIMIT 1",
        (platform, slug, cutoff),
    ).fetchone()
    return row is not None


def _write_manifest(artifact_dir: Path, payload: dict[str, Any]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def _write_signals_jsonl(artifact_dir: Path, sigs: list[Signal]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({
            "tool": s.tool, "signal_type": s.signal_type,
            "asset": s.asset, "target": s.target,
            "signature": s.signature, "payload": s.payload,
            "observed_at": s.observed_at,
        }) for s in sigs
    ]
    (artifact_dir / "signals.jsonl").write_text(
        "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
    )


def _write_required_artifacts(
    artifact_dir: Path,
    *,
    targets: list[str],
    raw_stdout: str,
    raw_stderr: str,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "input.txt").write_text(
        "\n".join(targets) + ("\n" if targets else ""), encoding="utf-8"
    )
    (artifact_dir / "raw.jsonl").write_text(raw_stdout, encoding="utf-8")
    (artifact_dir / "stderr.txt").write_text(raw_stderr, encoding="utf-8")


def run_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    tool_run: ToolRun,
    run_id: str | None = None,
) -> active.ActiveRunResult:
    """Gate-check → prereq freshness → load services → scan → filter → record."""
    s = active.check_gates(paths, platform, slug, mode="active")

    run_id = run_id or uuid.uuid4().hex
    now_dt = datetime.now(UTC)
    now = to_iso(now_dt)
    artifact_dir = paths.root / f"recon/outputs/{platform}/{slug}/nuclei/{now[:10]}/{run_id}"

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        if not _recent_httpx_success(conn, platform=platform, slug=slug, now=now_dt):
            return record_prereq_missing(
                conn, paths=paths, platform=platform, slug=slug,
                run_id=run_id, now=now, artifact_dir=artifact_dir, tool="nuclei",
                write_required_artifacts=_write_required_artifacts,
                write_signals_jsonl=_write_signals_jsonl,
                write_manifest=_write_manifest,
                prereq_freshness_hours=_PREREQ_FRESHNESS_HOURS,
            )

        targets = _load_in_scope_service_urls(conn, s)
        runs.start_run(
            conn, run_id=run_id, platform=platform, slug=slug, tool="nuclei",
            started_at=now, artifact_dir=str(artifact_dir), input_count=len(targets),
        )

        try:
            tool_result = tool_run(targets) if targets else active.ToolRunResult(outputs=())
        except Exception as exc:
            finished = now_iso()
            runs.finish_run(
                conn, run_id=run_id, finished_at=finished, status="failed",
                output_count=0, signal_count=0, source_failures=1, oos_drops=0,
                error_summary=f"{type(exc).__name__}: {exc}",
            )
            raise

        raw_signals: list[Signal] = list(tool_result.outputs)
        # B1: filter on both sig.asset AND sig.target (may redirect to OOS host).
        in_scope_sigs = [
            sig for sig in raw_signals
            if scope.is_in_scope(sig.asset, s.in_scope, s.out_of_scope)
            and scope.is_in_scope(
                target_host(sig.target, sig.asset), s.in_scope, s.out_of_scope,
            )
        ]
        oos_drops = len(raw_signals) - len(in_scope_sigs)

        if in_scope_sigs:
            signals.insert_signals(conn, in_scope_sigs)
        _write_signals_jsonl(artifact_dir, in_scope_sigs)
        _write_required_artifacts(
            artifact_dir,
            targets=targets,
            raw_stdout=tool_result.raw_stdout,
            raw_stderr=tool_result.raw_stderr,
        )
        _write_manifest(artifact_dir, {
            "run_id": run_id, "tool": "nuclei",
            "platform": platform, "slug": slug,
            "started_at": now, "input_count": len(targets),
            "signal_count": len(in_scope_sigs), "oos_drops": oos_drops,
            "approved_templates": sorted(APPROVED_TEMPLATE_DIRS),
        })

        run_status, terminated_reason = active.resolve_run_status(tool_result)

        finished = now_iso()
        runs.finish_run(
            conn, run_id=run_id, finished_at=finished, status=run_status,
            output_count=len(in_scope_sigs),
            signal_count=len(in_scope_sigs),
            source_failures=tool_result.source_failures, oos_drops=oos_drops,
            terminated_reason=terminated_reason,
        )
        return active.ActiveRunResult(
            run_id=run_id,
            targets_considered=len(targets),
            targets_scanned=len(targets),
            artifacts_written=1,
            signals_emitted=len(in_scope_sigs),
            source_failures=tool_result.source_failures,
            oos_drops=oos_drops,
            terminated_reason=terminated_reason,
        )
    finally:
        conn.close()
