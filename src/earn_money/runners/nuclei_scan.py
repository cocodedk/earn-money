"""Template-based vulnerability scan runner.

Mirrors httpx_probe but reads targets from `http_services` (the canonical
service inventory from Phase 3a) and writes `Signal` rows instead of
`HttpService` rows.  Every emitted signal is re-checked against the
program's scope (`oos_drops` counts the rejects).

Per spec section 7, the runner refuses to scan if there is no recent
successful httpx run (prereq freshness check).  The refusal is graceful:
a `prereq_missing` Signal is written and the recon_runs row is marked
`status='skipped'`.

CLI entry-point and real-tool wiring live in nuclei_scan_cli.py so this
file stays under the 200-line cap.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from earn_money import config, db, scope
from earn_money.recon import runs, signals
from earn_money.recon.nuclei_tool import APPROVED_TEMPLATE_DIRS
from earn_money.recon.signals import Signal
from earn_money.runners import active

ToolRun = Callable[[list[str]], active.ToolRunResult]

_PREREQ_FRESHNESS_HOURS = 24


def _target_host(target: str, fallback: str) -> str:
    """Extract the hostname from a URL for OOS checking (B1).

    If `target` has no scheme or cannot be parsed, fall back to `fallback`
    (typically ``sig.asset``) so callers get a consistent non-empty string.
    """
    if "://" in target:
        return urlparse(target).hostname or fallback
    return fallback


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
    cutoff = (now - timedelta(hours=_PREREQ_FRESHNESS_HOURS)).isoformat(
        timespec="seconds"
    )
    row = conn.execute(
        "SELECT 1 FROM recon_runs WHERE platform = ? AND slug = ? "
        "AND tool = 'httpx' AND status IN ('success', 'partial') "
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
    with (artifact_dir / "signals.jsonl").open("w", encoding="utf-8") as fh:
        for s in sigs:
            fh.write(json.dumps({
                "tool": s.tool, "signal_type": s.signal_type,
                "asset": s.asset, "target": s.target,
                "signature": s.signature, "payload": s.payload,
                "observed_at": s.observed_at,
            }) + "\n")


def _write_required_artifacts(
    artifact_dir: Path,
    *,
    targets: list[str],
    raw_stdout: str,
    raw_stderr: str,
) -> None:
    """P1.2: write the three required Shared Artifact Contract files.

    Every nuclei run dir must contain:
    - input.txt  — newline-separated target URLs fed to nuclei
    - raw.jsonl  — captured stdout (nuclei JSONL output before parsing)
    - stderr.txt — captured stderr
    """
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
    now = now_dt.isoformat(timespec="seconds")
    artifact_dir = paths.root / (
        f"recon/outputs/{platform}/{slug}/nuclei/{now[:10]}/{run_id}"
    )

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        if not _recent_httpx_success(conn, platform=platform, slug=slug, now=now_dt):
            return _record_prereq_missing(
                conn, platform, slug, run_id, now, artifact_dir,
            )

        targets = _load_in_scope_service_urls(conn, s)
        runs.start_run(
            conn, run_id=run_id, platform=platform, slug=slug, tool="nuclei",
            started_at=now, artifact_dir=str(artifact_dir), input_count=len(targets),
        )

        try:
            tool_result = (
                tool_run(targets) if targets
                else active.ToolRunResult(services=())
            )
        except Exception as exc:
            finished = datetime.now(UTC).isoformat(timespec="seconds")
            runs.finish_run(
                conn, run_id=run_id, finished_at=finished, status="failed",
                output_count=0, signal_count=0, source_failures=1, oos_drops=0,
                error_summary=f"{type(exc).__name__}: {exc}",
            )
            raise

        raw_signals: list[Signal] = list(tool_result.services)
        # B1: check BOTH sig.asset (the host nuclei probed) AND sig.target
        # (the actual matched URL, which may redirect to an OOS host).
        in_scope_sigs = [
            sig for sig in raw_signals
            if scope.is_in_scope(sig.asset, s.in_scope, s.out_of_scope)
            and scope.is_in_scope(
                _target_host(sig.target, sig.asset), s.in_scope, s.out_of_scope,
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

        terminated_reason: str | None = (
            tool_result.terminated_reason
            or ("kill_switch" if tool_result.aborted else None)
            or ("timeout" if tool_result.timed_out else None)
        )
        run_status = "partial" if terminated_reason else "success"

        finished = datetime.now(UTC).isoformat(timespec="seconds")
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
        )
    finally:
        conn.close()


def _record_prereq_missing(
    conn: sqlite3.Connection,
    platform: str,
    slug: str,
    run_id: str,
    now: str,
    artifact_dir: Path,
) -> active.ActiveRunResult:
    runs.start_run(
        conn, run_id=run_id, platform=platform, slug=slug, tool="nuclei",
        started_at=now, artifact_dir=str(artifact_dir), input_count=0,
    )
    prereq_sig = Signal(
        run_id=run_id, tool="nuclei", signal_type="prereq_missing",
        asset="", target="",
        signature=f"prereq|httpx|<{_PREREQ_FRESHNESS_HOURS}h",
        payload=json.dumps({
            "required_tool": "httpx",
            "max_age_hours": _PREREQ_FRESHNESS_HOURS,
        }),
        observed_at=now,
    )
    signals.insert_signals(conn, [prereq_sig])
    _write_signals_jsonl(artifact_dir, [prereq_sig])
    _write_required_artifacts(artifact_dir, targets=[], raw_stdout="", raw_stderr="")
    _write_manifest(artifact_dir, {
        "run_id": run_id, "tool": "nuclei",
        "platform": platform, "slug": slug, "started_at": now,
        "status": "skipped", "reason": "no recent httpx run",
    })
    finished = datetime.now(UTC).isoformat(timespec="seconds")
    runs.finish_run(
        conn, run_id=run_id, finished_at=finished, status="skipped",
        output_count=0, signal_count=1, source_failures=0, oos_drops=0,
        error_summary="no recent httpx run within prereq freshness window",
    )
    return active.ActiveRunResult(
        run_id=run_id, targets_considered=0, targets_scanned=0,
        artifacts_written=1, signals_emitted=1, source_failures=0, oos_drops=0,
    )
