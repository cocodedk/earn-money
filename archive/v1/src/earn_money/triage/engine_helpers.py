"""Private helpers extracted from `engine.py` to keep that file under
the 200-line cap. Public API is `engine.run_program`; these are internal.
"""

from __future__ import annotations

import json
import sqlite3

from earn_money.recon.signals import Signal
from earn_money.triage.findings import Finding


def build_finding(
    sig: Signal,
    *,
    finding_hash: str,
    platform: str,
    slug: str,
    vuln_class: str,
    title: str,
    severity_hint: str,
    confidence: int,
    evidence_path: str,
    notes_path: str,
    existing: Finding | None,
    now: str,
) -> Finding:
    """Build the Finding row for a signal observation, carrying first_seen +
    occurrence_count forward from any existing row."""
    return Finding(
        finding_hash=finding_hash,
        platform=platform, slug=slug,
        vuln_class=vuln_class,
        asset=sig.asset, target=sig.target, signature=sig.signature,
        title=title, severity_hint=severity_hint, confidence=confidence,
        source_tool=sig.tool, source_run_id=sig.run_id,
        evidence_path=evidence_path, notes_path=notes_path,
        first_seen=existing.first_seen if existing else sig.observed_at,
        last_seen=sig.observed_at,
        occurrence_count=(existing.occurrence_count if existing else 1),
        current_state=(existing.current_state if existing else "queued"),
        state_changed_at=(existing.state_changed_at if existing else now),
        external_report_id=existing.external_report_id if existing else None,
        payout_amount=existing.payout_amount if existing else None,
        payout_currency=existing.payout_currency if existing else None,
    )


def template_version(payload: str) -> str:
    """Best-effort extraction of `info.version` from a nuclei JSON payload.

    Real nuclei rarely emits this field; returns ``'unknown'`` otherwise."""
    try:
        info = json.loads(payload).get("info", {})
    except (json.JSONDecodeError, AttributeError):
        return "unknown"
    if not isinstance(info, dict):
        return "unknown"
    return str(info.get("version", "unknown"))


def evidence_path(conn: sqlite3.Connection, run_id: str) -> str:
    row = conn.execute(
        "SELECT artifact_dir FROM recon_runs WHERE run_id = ?", (run_id,),
    ).fetchone()
    if not row:
        return ""
    return f"{row[0]}/raw.jsonl"
