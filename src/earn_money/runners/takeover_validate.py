"""Subdomain-takeover validation runner.

Hands in-scope subdomains to subzy. Subzy fingerprints each host's
DNS resolution chain against SaaS-provider response patterns and
flags only confirmed-vulnerable entries. Signals land in the
existing `signals` table; the operator promotes them via the same
two-gate workflow as any other finding.

Independent of httpx — subzy resolves DNS itself, so the only
prereq is the `assets` table being populated by passive_recon.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from pathlib import Path

from earn_money import config, db, roe, scope
from earn_money._time import now_iso
from earn_money.recon import runs, signals
from earn_money.recon.signals import Signal
from earn_money.runners import active

ToolRun = Callable[[list[str]], active.ToolRunResult]


def _load_in_scope_subdomains(
    conn: sqlite3.Connection, s: scope.Scope
) -> list[str]:
    """Return in-scope subdomains, explicit-first then alphabetical.

    Same sort rationale as the httpx runner: program-authored entries
    come before wildcard fan-out, so `max_targets` picks operator-
    facing assets first.
    """
    cursor = conn.execute(
        "SELECT subdomain FROM assets WHERE in_scope_at_observation = 1"
    )
    matches = [
        row[0] for row in cursor
        if scope.is_in_scope(row[0], s.in_scope, s.out_of_scope)
    ]
    explicit = scope.explicit_literals(s.in_scope)
    return sorted(matches, key=lambda h: (h.lower() not in explicit, h))


def _write_manifest(artifact_dir: Path, payload: dict[str, object]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def _write_signals_jsonl(
    artifact_dir: Path, sigs: list[Signal]
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({
            "tool": s.tool, "signal_type": s.signal_type,
            "asset": s.asset, "target": s.target,
            "signature": s.signature, "payload": s.payload,
            "observed_at": s.observed_at,
        })
        for s in sigs
    ]
    (artifact_dir / "signals.jsonl").write_text(
        "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
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
    """Gate-check → load assets → invoke subzy → scope-filter signals → record."""
    s = active.check_gates(paths, platform, slug, mode="active")
    program_roe = roe.read_roe(paths.roe_file(platform, slug))

    run_id = run_id or uuid.uuid4().hex
    now = now_iso()
    artifact_dir = paths.root / (
        f"recon/outputs/{platform}/{slug}/subzy/{now[:10]}/{run_id}"
    )

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        targets = _load_in_scope_subdomains(conn, s)
        if max_targets is not None and max_targets >= 0:
            targets = targets[:max_targets]

        runs.start_run(
            conn, run_id=run_id, platform=platform, slug=slug, tool="subzy",
            started_at=now, artifact_dir=str(artifact_dir),
            input_count=len(targets),
        )

        try:
            tool_result = (
                tool_run(targets) if targets else active.ToolRunResult(outputs=())
            )
        except Exception as exc:
            finished = now_iso()
            runs.finish_run(
                conn, run_id=run_id, finished_at=finished, status="failed",
                output_count=0, signal_count=0, source_failures=1, oos_drops=0,
                error_summary=f"{type(exc).__name__}: {exc}",
            )
            raise

        raw_sigs: list[Signal] = list(tool_result.outputs)
        in_scope_sigs = [
            sig for sig in raw_sigs
            if scope.is_in_scope(sig.asset, s.in_scope, s.out_of_scope)
        ]
        oos_drops = len(raw_sigs) - len(in_scope_sigs)

        if in_scope_sigs:
            signals.insert_signals(conn, in_scope_sigs)
        _write_signals_jsonl(artifact_dir, in_scope_sigs)
        _write_manifest(artifact_dir, {
            "run_id": run_id, "tool": "subzy",
            "platform": platform, "slug": slug,
            "started_at": now, "input_count": len(targets),
            "signal_count": len(in_scope_sigs), "oos_drops": oos_drops,
            "roe": program_roe.manifest_payload(),
        })

        run_status, terminated_reason = active.resolve_run_status(tool_result)
        finished = now_iso()
        error_summary = (
            None if tool_result.source_failures <= 0
            else f"{tool_result.source_failures} batch(es) failed: "
                 f"{tool_result.raw_stderr[:200].strip() or '(empty stderr)'}"
        )
        runs.finish_run(
            conn, run_id=run_id, finished_at=finished, status=run_status,
            output_count=len(in_scope_sigs),
            signal_count=len(in_scope_sigs),
            source_failures=tool_result.source_failures, oos_drops=oos_drops,
            terminated_reason=terminated_reason,
            error_summary=error_summary,
        )
        return active.ActiveRunResult(
            run_id=run_id,
            targets_considered=len(targets),
            targets_scanned=len(targets),
            artifacts_written=1,
            outputs_recorded=len(in_scope_sigs),
            source_failures=tool_result.source_failures,
            oos_drops=oos_drops,
            terminated_reason=terminated_reason,
        )
    finally:
        conn.close()
