"""Routing helper: send a rule-matched finding directly to `_resolved/info/`
with a structured audit row, instead of `_queue/`.

The engine calls `apply()` when `rules.match()` returns a Rule for a new
finding. Existing-finding refreshes never reach this module — suppression
only applies at first observation.
"""

from __future__ import annotations

import dataclasses
import sqlite3

from earn_money import config
from earn_money.recon import services
from earn_money.recon.services import pick_canonical_service
from earn_money.triage import findings, history, queue
from earn_money.triage.findings import Finding
from earn_money.triage.rules import Rule


def apply(
    conn: sqlite3.Connection,
    paths: config.Paths,
    finding: Finding,
    rule: Rule,
    *,
    version: str,
    now: str,
) -> None:
    """Insert the finding in `_resolved/info/` and write the audit row.

    The DAO requires new rows to start in `queued`. We insert, then call
    ``history.transition_state`` to flip to ``resolved_info``. Both the
    INSERT and the transition write through the same SQLite connection,
    so the operator only ever sees the post-transition state.
    """
    notes_path = f"findings/_resolved/info/{finding.finding_hash}.md"
    new_finding = dataclasses.replace(finding, notes_path=notes_path)
    findings.upsert_finding(conn, new_finding)

    svc = pick_canonical_service(services.services_for_subdomains(conn, [finding.asset]))
    body_path = paths.root / notes_path
    body_path.parent.mkdir(parents=True, exist_ok=True)
    body_path.write_text(queue.render(new_finding, service=svc), encoding="utf-8")

    note = (
        f"rule={rule.name} template={finding.vuln_class} "
        f"version={version} reason={rule.reason}"
    )
    history.transition_state(
        conn,
        finding_hash=finding.finding_hash,
        to_state="resolved_info",
        actor="triage-engine",
        note=note,
        now=now,
    )
