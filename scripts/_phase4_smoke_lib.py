"""Fixtures and helpers for scripts/smoke-phase4-loop.py.

Kept separate so the orchestration script stays under the 200-line cap.
Public API: _FINDINGS, setup_tree, seed_findings, render_queue_files,
transition, run_bin, synth_frozen_scenario, dump_ledger.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from earn_money import config, db
from earn_money import scope as scope_mod
from earn_money._time import now_iso
from earn_money.triage import findings, history, queue

PLATFORM, SLUG = "demo", "proof"

# Four synthetic findings, one per state-machine path the smoke exercises.
_FINDINGS: list[dict[str, object]] = [
    {
        "finding_hash": "f1" + "0" * 62, "vuln_class": "cve-2023-1234",
        "asset": "api.demo.test", "target": "https://api.demo.test/v1",
        "signature": "cve-2023-1234|primary|",
        "title": "CVE-2023-1234 nuclei hit on api.demo.test",
        "severity_hint": "medium", "confidence": 72,
        "label": "F1: full happy path → submitted → N/A",
    },
    {
        "finding_hash": "f2" + "0" * 62, "vuln_class": "csp-script-src-wildcard",
        "asset": "app.demo.test", "target": "https://app.demo.test/",
        "signature": "csp-script-src-wildcard||",
        "title": "CSP wildcard on app.demo.test",
        "severity_hint": "info", "confidence": 30,
        "label": "F2: direct-dismiss queued → resolved_info",
    },
    {
        "finding_hash": "f3" + "0" * 62, "vuln_class": "open-redirect",
        "asset": "auth.demo.test",
        "target": "https://auth.demo.test/login?next=//evil",
        "signature": "open-redirect|next-param|",
        "title": "Open redirect on auth.demo.test",
        "severity_hint": "low", "confidence": 60,
        "label": "F3: queued → verified → drafted → submitted (awaiting)",
    },
    {
        "finding_hash": "f4" + "0" * 62,
        "vuln_class": "missing-cookie-samesite-strict",
        "asset": "api.demo.test", "target": "https://api.demo.test/v1",
        "signature": "missing-cookie-samesite-strict||",
        "title": "samesite=lax on api.demo.test session cookie",
        "severity_hint": "info", "confidence": 30,
        "label": "F4: queued → resolved_dupe (dupe of F1)",
    },
]


def setup_tree(repo: Path) -> Path:
    """Create a fresh tmpdir with templates/ copied and the demo scope.md."""
    root = Path(tempfile.mkdtemp(prefix="phase4-smoke-"))
    shutil.copytree(repo / "templates", root / "templates")
    paths = config.Paths.from_root(root)
    scope_mod.write_scope(
        paths.scope_file(PLATFORM, SLUG),
        scope_mod.Scope(
            platform=PLATFORM, slug=SLUG, policy="rate-limited-OK",
            in_scope=["*.demo.test"], out_of_scope=[],
            notes="", scope_hash="seed", last_synced=now_iso(),
        ),
    )
    return root


def seed_findings(paths: config.Paths) -> None:
    conn = db.open_db(paths.program_db(PLATFORM, SLUG))
    try:
        for f in _FINDINGS:
            findings.upsert_finding(conn, findings.Finding(
                finding_hash=f["finding_hash"], platform=PLATFORM, slug=SLUG,
                vuln_class=f["vuln_class"], asset=f["asset"], target=f["target"],
                signature=f["signature"], title=f["title"],
                severity_hint=f["severity_hint"], confidence=f["confidence"],
                source_tool="nuclei", source_run_id="proof-run",
                evidence_path="recon/outputs/.../raw.jsonl",
                notes_path=f"findings/_queue/{f['finding_hash']}.md",
                first_seen=now_iso(), last_seen=now_iso(), occurrence_count=1,
                current_state="queued", state_changed_at=now_iso(),
                external_report_id=None, payout_amount=None, payout_currency=None,
            ))
        conn.commit()
    finally:
        conn.close()


def render_queue_files(root: Path) -> None:
    qdir = root / "findings" / "_queue"
    qdir.mkdir(parents=True, exist_ok=True)
    paths = config.Paths.from_root(root)
    conn = db.open_db(paths.program_db(PLATFORM, SLUG))
    try:
        for f in _FINDINGS:
            finding = findings.find_by_hash(conn, f["finding_hash"])  # type: ignore[arg-type]
            assert finding is not None
            (qdir / f"{f['finding_hash']}.md").write_text(
                queue.render(finding, service=None), encoding="utf-8"
            )
    finally:
        conn.close()


def transition(paths: config.Paths, *, fh: str, to: str, actor: str, note: str) -> None:
    conn = db.open_db(paths.program_db(PLATFORM, SLUG))
    try:
        history.transition_state(
            conn, finding_hash=fh, to_state=to,  # type: ignore[arg-type]
            actor=actor, note=note, now=now_iso(),
        )
    finally:
        conn.close()


def run_bin(repo: Path, root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a bin/<name> CLI with --root pointed at the tmpdir."""
    return subprocess.run(
        [str(repo / "bin" / args[0]),
         "--root", str(root), "--platform", PLATFORM,
         "--program", SLUG, *args[1:]],
        capture_output=True, text=True,
    )


def synth_frozen_scenario(repo: Path, root: Path) -> subprocess.CompletedProcess[str]:
    """Touch FROZEN, run bin/ack-freeze with $EDITOR stub."""
    prog_dir = root / "programs" / PLATFORM / SLUG
    (prog_dir / "FROZEN").write_text(
        "scope removed asset 'api.demo.test' at " + now_iso() + "\n",
        encoding="utf-8",
    )
    editor = root / "_smoke_editor.sh"
    editor.write_text(
        "#!/bin/sh\necho 'rescoped; asset re-added by program owner.' > \"$1\"\n",
        encoding="utf-8",
    )
    editor.chmod(0o755)
    return subprocess.run(
        [str(repo / "bin" / "ack-freeze"), f"{PLATFORM}/{SLUG}"],
        env={**os.environ, "ACK_FREEZE_ROOT": str(root), "EDITOR": str(editor)},
        capture_output=True, text=True,
    )


def dump_ledger(root: Path) -> str:
    """Render a markdown ledger of every finding's final state + audit trail."""
    paths = config.Paths.from_root(root)
    conn = sqlite3.connect(paths.program_db(PLATFORM, SLUG))
    try:
        lines: list[str] = [
            "# Phase 4 state-machine proof — ledger", "",
            f"Generated: {now_iso()}  ·  Demo root: `{root}`", "",
            "## Findings (final state)", "",
            "| Hash | Vuln class | State | External ID |",
            "|---|---|---|---|",
        ]
        for r in conn.execute(
            "SELECT finding_hash, vuln_class, current_state, external_report_id "
            "FROM findings ORDER BY finding_hash"
        ):
            fh, vc, st, ext = r
            lines.append(f"| `{fh[:8]}…` | {vc} | `{st}` | {ext or '—'} |")
        lines += ["", "## Audit history (every transition)", ""]
        for fh, vc in conn.execute(
            "SELECT finding_hash, vuln_class FROM findings ORDER BY finding_hash"
        ):
            lines += [f"### `{fh[:8]}…` — {vc}", ""]
            for r in conn.execute(
                "SELECT changed_at, from_state, to_state, actor, note "
                "FROM findings_state_history WHERE finding_hash=? ORDER BY id",
                (fh,),
            ):
                ts, frm, to, actor, note = r
                lines.append(
                    f"- `{ts}`  **{frm or '∅'} → {to}**  · {actor}  · _{note or '—'}_"
                )
            lines.append("")
    finally:
        conn.close()
    ack_log = root / "programs" / PLATFORM / SLUG / "freeze-acks.log"
    if ack_log.exists():
        lines += ["## Freeze-acks log", "", "```",
                  ack_log.read_text(encoding="utf-8").rstrip(), "```"]
    return "\n".join(lines) + "\n"
