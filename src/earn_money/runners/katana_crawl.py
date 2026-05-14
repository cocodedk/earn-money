"""Katana crawler runner.

Walks links from in-scope HTTP services and writes discovered URLs as
`discovered_urls.jsonl` artifact. Does NOT insert into `signals` —
discovered URLs are operator-facing context, not findings. v2 may
flow them into nuclei's target list; for now they live on disk only.

Same gate/RoE/manifest pattern as the other active runners. Independent
of nuclei but shares the httpx prereq (services must be alive).
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from earn_money import config, db, roe, scope
from earn_money._time import now_iso, to_iso
from earn_money.recon import runs
from earn_money.recon.katana_tool import DiscoveredUrl, filter_in_scope
from earn_money.runners import active, nuclei_artifacts
from earn_money.runners._prereq import record_prereq_missing

ToolRun = Callable[[list[str]], active.ToolRunResult]

_PREREQ_FRESHNESS_HOURS = 24


def _load_in_scope_service_urls(
    conn: sqlite3.Connection, s: scope.Scope
) -> list[str]:
    """Same shape as nuclei: in-scope URLs, explicit-first."""
    cursor = conn.execute(
        "SELECT url, subdomain, scheme, port FROM http_services "
        "WHERE in_scope_at_observation = 1"
    )
    matches = [
        (url, subdomain, scheme, port) for url, subdomain, scheme, port in cursor
        if scope.is_in_scope(subdomain, s.in_scope, s.out_of_scope)
    ]
    explicit = scope.explicit_literals(s.in_scope)
    matches.sort(
        key=lambda r: (r[1].lower() not in explicit, r[1], r[2], r[3]),
    )
    return [url for url, _, _, _ in matches]


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


def _write_discovered_urls_jsonl(
    artifact_dir: Path, urls: list[DiscoveredUrl]
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({
            "url": u.url,
            "status_code": u.status_code,
            "content_type": u.content_type,
            "method": u.method,
        })
        for u in urls
    ]
    (artifact_dir / "discovered_urls.jsonl").write_text(
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
    """Gate → prereq → load services → katana → scope-filter → record."""
    s = active.check_gates(paths, platform, slug, mode="active")
    program_roe = roe.read_roe(paths.roe_file(platform, slug))

    run_id = run_id or uuid.uuid4().hex
    now_dt = datetime.now(UTC)
    now = to_iso(now_dt)
    artifact_dir = paths.root / (
        f"recon/outputs/{platform}/{slug}/katana/{now[:10]}/{run_id}"
    )

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        if not _recent_httpx_success(conn, platform=platform, slug=slug, now=now_dt):
            return record_prereq_missing(
                conn, paths=paths, platform=platform, slug=slug,
                run_id=run_id, now=now, artifact_dir=artifact_dir, tool="katana",
                write_required_artifacts=nuclei_artifacts.write_required_artifacts,
                write_signals_jsonl=nuclei_artifacts.write_signals_jsonl,
                write_manifest=nuclei_artifacts.write_manifest,
                prereq_freshness_hours=_PREREQ_FRESHNESS_HOURS,
            )

        targets = _load_in_scope_service_urls(conn, s)
        if max_targets is not None and max_targets >= 0:
            targets = targets[:max_targets]

        runs.start_run(
            conn, run_id=run_id, platform=platform, slug=slug, tool="katana",
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

        discovered: list[DiscoveredUrl] = [
            u for u in tool_result.outputs if isinstance(u, DiscoveredUrl)
        ]
        in_scope, oos_drops = filter_in_scope(
            discovered,
            in_scope_host=lambda h: scope.is_in_scope(h, s.in_scope, s.out_of_scope),
        )

        _write_discovered_urls_jsonl(artifact_dir, in_scope)
        nuclei_artifacts.write_required_artifacts(
            artifact_dir,
            targets=targets,
            raw_stdout=tool_result.raw_stdout,
            raw_stderr=tool_result.raw_stderr,
        )
        nuclei_artifacts.write_manifest(artifact_dir, {
            "run_id": run_id, "tool": "katana",
            "platform": platform, "slug": slug,
            "started_at": now, "input_count": len(targets),
            "discovered_count": len(in_scope), "oos_drops": oos_drops,
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
            output_count=len(in_scope), signal_count=0,
            source_failures=tool_result.source_failures, oos_drops=oos_drops,
            terminated_reason=terminated_reason,
            error_summary=error_summary,
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
