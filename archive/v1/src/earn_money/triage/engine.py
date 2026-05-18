"""Triage engine v1.

Reads finished recon runs that have `triaged_at IS NULL`, fetches their
signals, computes finding hashes, upserts `findings` rows, and writes
`findings/_queue/<hash>.md` for freshly-created findings only.

Re-observation rules:
- A signal whose hash matches an existing non-terminal finding refreshes
  `last_seen`, increments `occurrence_count`, and updates evidence —
  but does NOT rewrite the queue markdown (operator edits are sacred).
- A signal whose hash matches a terminal finding (resolved_*) is a no-op
  at the row level. The signal still counts toward the `findings_refreshed`
  result so the digest can surface "old finding re-observed" rows.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from earn_money import config, db, flags, scope
from earn_money._time import now_iso
from earn_money.recon import services
from earn_money.recon.services import pick_canonical_service
from earn_money.recon.signals import Signal
from earn_money.recon.urls import target_host
from earn_money.triage import engine_helpers, findings, hashing, queue, rules, suppress
from earn_money.triage.classify import classify


@dataclass(frozen=True)
class TriageRunResult:
    runs_processed: int
    findings_created: int
    findings_refreshed: int
    signals_skipped: int


def run_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    now: str | None = None,
) -> TriageRunResult:
    """Triage every untriaged finished recon_runs row for this program.

    Triage does NOT call active.check_gates(mode='active') because it
    sends no target traffic. We still respect kill-switch + freeze so the
    operator can halt all per-program work in one place.
    """
    now = now or now_iso()

    flags.require_recon_enabled(paths)
    flags.require_program_not_frozen(paths, platform, slug)
    s = scope.read_scope(paths.scope_file(platform, slug))
    rs = rules.load_rules(paths.root / "triage_rules.yaml")

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        untriaged_rows = conn.execute(
            "SELECT run_id, tool FROM recon_runs "
            "WHERE platform = ? AND slug = ? "
            "AND finished_at IS NOT NULL AND triaged_at IS NULL "
            "ORDER BY started_at",
            (platform, slug),
        ).fetchall()

        created = 0
        refreshed = 0
        skipped = 0

        for run_id, _tool in untriaged_rows:
            sigs = _signals_for_run(conn, run_id)
            for sig in sigs:
                outcome = _process_signal(
                    conn, paths, sig, scope_=s,
                    platform=platform, slug=slug, now=now, rules_=rs,
                )
                if outcome == "created":
                    created += 1
                elif outcome == "refreshed":
                    refreshed += 1
                else:
                    skipped += 1
            conn.execute(
                "UPDATE recon_runs SET triaged_at = ? WHERE run_id = ?",
                (now, run_id),
            )
            conn.commit()

        return TriageRunResult(
            runs_processed=len(untriaged_rows),
            findings_created=created,
            findings_refreshed=refreshed,
            signals_skipped=skipped,
        )
    finally:
        conn.close()


def _signals_for_run(conn: sqlite3.Connection, run_id: str) -> list[Signal]:
    cursor = conn.execute(
        "SELECT run_id, tool, signal_type, asset, target, signature, "
        "payload, observed_at FROM signals WHERE run_id = ? ORDER BY id",
        (run_id,),
    )
    return [Signal(*row) for row in cursor]


def _process_signal(
    conn: sqlite3.Connection,
    paths: config.Paths,
    sig: Signal,
    *,
    scope_: scope.Scope,
    platform: str,
    slug: str,
    now: str,
    rules_: list[rules.Rule],
) -> str:
    """Triage one signal. Returns one of: 'created', 'refreshed', 'skipped'."""
    # Defensive scope re-check: scope can tighten between scan and triage time.
    if sig.asset and not scope.is_in_scope(
        sig.asset, scope_.in_scope, scope_.out_of_scope
    ):
        return "skipped"
    if sig.target:
        t_host = target_host(sig.target, sig.asset)
        if t_host and not scope.is_in_scope(
            t_host, scope_.in_scope, scope_.out_of_scope
        ):
            return "skipped"

    vuln_class, title, severity_hint, confidence = classify(sig)
    finding_hash = hashing.compute_hash(
        platform=platform, slug=slug, vuln_class=vuln_class,
        asset=sig.asset, target=sig.target, signature=sig.signature,
    )

    existing = findings.find_by_hash(conn, finding_hash)
    rule = rules.match(rules_, vuln_class=vuln_class, severity=severity_hint)
    ev_path = engine_helpers.evidence_path(conn, sig.run_id)
    notes_path = f"findings/_queue/{finding_hash}.md"
    finding = engine_helpers.build_finding(
        sig, finding_hash=finding_hash, platform=platform, slug=slug,
        vuln_class=vuln_class, title=title, severity_hint=severity_hint,
        confidence=confidence, evidence_path=ev_path,
        notes_path=notes_path, existing=existing, now=now,
    )

    if existing is None and rule is not None:
        suppress.apply(
            conn, paths, finding, rule,
            version=engine_helpers.template_version(sig.payload), now=now,
        )
        return "created"

    findings.upsert_finding(conn, finding)

    if existing is None:
        svc = pick_canonical_service(services.services_for_subdomains(conn, [sig.asset]))
        queue_path = paths.root / notes_path
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        queue_path.write_text(queue.render(finding, service=svc), encoding="utf-8")
        return "created"
    return "refreshed"




