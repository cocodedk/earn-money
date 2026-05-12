"""Shared helper: write a `prereq_missing` signal + skipped recon_runs row.

Used by active runners that depend on a recent successful httpx run
(nuclei in 3b; katana + ffuf in 3c). The runner calls this helper when
the prereq freshness check fails. The skipped run is a proper audit
record, not a silent no-op.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from earn_money import config
from earn_money._time import now_iso
from earn_money.recon import runs, signals
from earn_money.recon.signals import Signal
from earn_money.runners import active


def record_prereq_missing(
    conn: sqlite3.Connection,
    *,
    paths: config.Paths,
    platform: str,
    slug: str,
    run_id: str,
    now: str,
    artifact_dir: Path,
    tool: str,
    write_required_artifacts: Callable[..., None],
    write_signals_jsonl: Callable[[Path, list[Signal]], None],
    write_manifest: Callable[[Path, dict[str, Any]], None],
    prereq_freshness_hours: int,
) -> active.ActiveRunResult:
    """Common skip-with-audit path when a recent httpx prereq is missing.

    The three writer callables are injected so each runner can keep its
    own filename conventions. All five required artifact files are
    written (per the Shared Artifact Contract).
    """
    runs.start_run(
        conn, run_id=run_id, platform=platform, slug=slug, tool=tool,
        started_at=now, artifact_dir=str(artifact_dir), input_count=0,
    )
    prereq_sig = Signal(
        run_id=run_id, tool=tool, signal_type="prereq_missing",
        asset="", target="",
        signature=f"prereq|httpx|<{prereq_freshness_hours}h",
        payload=json.dumps({
            "required_tool": "httpx",
            "max_age_hours": prereq_freshness_hours,
        }),
        observed_at=now,
    )
    signals.insert_signals(conn, [prereq_sig])
    write_signals_jsonl(artifact_dir, [prereq_sig])
    write_required_artifacts(artifact_dir, targets=[], raw_stdout="", raw_stderr="")
    write_manifest(artifact_dir, {
        "run_id": run_id, "tool": tool,
        "platform": platform, "slug": slug, "started_at": now,
        "status": "skipped", "reason": "no recent httpx run",
    })
    finished = now_iso()
    runs.finish_run(
        conn, run_id=run_id, finished_at=finished, status="skipped",
        output_count=0, signal_count=1, source_failures=0, oos_drops=0,
        error_summary="no recent httpx run within prereq freshness window",
    )
    return active.ActiveRunResult(
        run_id=run_id, targets_considered=0, targets_scanned=0,
        artifacts_written=1, outputs_recorded=0, source_failures=0, oos_drops=0,
        prereq_skipped=True,
    )
