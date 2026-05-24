"""End-to-end smoke for the Phase 4 submission loop in an isolated tmp tree.

Exercises every state-machine transition + bin/ack-freeze against the
real installed CLIs — not touching any real program's data. Designed
to run on the VPS or locally. Reproducible: each run produces the
same logical state with fresh timestamps.

Usage:
    .venv/bin/python scripts/smoke-phase4-loop.py

Fixtures + ledger renderer live in scripts/_phase4_smoke_lib.py.
This smoke targets the archived v1 CLI corpus under archive/v1.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
V1_REPO = REPO / "archive" / "v1"
sys.path.insert(0, str(V1_REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from _phase4_smoke_lib import (  # noqa: E402
    _FINDINGS,
    dump_ledger,
    render_queue_files,
    run_bin,
    seed_findings,
    setup_tree,
    synth_frozen_scenario,
    transition,
)

from earn_money import config  # noqa: E402


def preflight() -> None:
    """Fail early when the archived v1 CLI runtime is not installed."""
    missing: list[str] = []
    if not (V1_REPO / ".venv" / "bin" / "python").is_file():
        missing.append("archive/v1/.venv/bin/python")
    for name in ("draft", "submit", "ack-freeze"):
        if not (V1_REPO / "bin" / name).is_file():
            missing.append(f"archive/v1/bin/{name}")
    if missing:
        print("smoke-phase4-loop: archived v1 runtime is not ready", file=sys.stderr)
        for item in missing:
            print(f"  missing: {item}", file=sys.stderr)
        print("run: cd archive/v1 && make install-dev", file=sys.stderr)
        raise SystemExit(1)


def step(n: int, label: str) -> None:
    print(f"\n── {n}. {label} " + "─" * max(0, 60 - len(label)))


def _phase_1_setup(paths: config.Paths, root: Path) -> None:
    seed_findings(paths)
    render_queue_files(root)
    print(f"  demo root: {root}")
    for f in _FINDINGS:
        print(f"  - {f['finding_hash'][:8]}…  ({f['label']})")


def _phase_2_full_happy_path(paths: config.Paths, root: Path) -> None:
    """F1: queued → verified → submitted → resolved_na."""
    fh: str = _FINDINGS[0]["finding_hash"]  # type: ignore[assignment]
    transition(paths, fh=fh, to="verified", actor="operator",
               note="reproduced manually; impact: cookie-flag info")
    res = run_bin(V1_REPO, root, ["draft", "--hash", fh])
    print(f"  bin/draft exit={res.returncode}  stdout: {res.stdout.strip()}")
    res = run_bin(V1_REPO, root, [
        "submit", "--hash", fh,
        "--report-id", "H1-PROOF-001",
        "--note", "SMOKE: state-machine proof, not actually filed",
    ])
    print(f"  bin/submit exit={res.returncode}  stdout: {res.stdout.strip()}")
    transition(paths, fh=fh, to="resolved_na", actor="platform-proxy",
               note="SMOKE: simulating platform N/A response for info-class finding")


def _phase_3_direct_dismiss(paths: config.Paths) -> None:
    """F2: queued → resolved_info (operator dismisses scanner noise)."""
    transition(paths, fh=_FINDINGS[1]["finding_hash"], to="resolved_info",  # type: ignore[arg-type]
               actor="operator",
               note="scanner noise; CSP wildcards intentional on this app")


def _phase_4_filed_awaiting(paths: config.Paths, root: Path) -> None:
    """F3: queued → verified → submitted (stops there — awaiting platform)."""
    fh: str = _FINDINGS[2]["finding_hash"]  # type: ignore[assignment]
    transition(paths, fh=fh, to="verified", actor="operator",
               note="reproduced; open-redirect via ?next=//evil")
    res = run_bin(V1_REPO, root, ["draft", "--hash", fh])
    print(f"  bin/draft exit={res.returncode}  stdout: {res.stdout.strip()}")
    res = run_bin(V1_REPO, root, [
        "submit", "--hash", fh,
        "--report-id", "H1-PROOF-002",
        "--note", "SMOKE: filed, awaiting platform response",
    ])
    print(f"  bin/submit exit={res.returncode}  stdout: {res.stdout.strip()}")


def _phase_5_resolved_dupe(paths: config.Paths) -> None:
    """F4: queued → resolved_dupe (operator marks dupe of F1)."""
    transition(
        paths, fh=_FINDINGS[3]["finding_hash"], to="resolved_dupe",  # type: ignore[arg-type]
        actor="operator",
        note=f"dupe of {_FINDINGS[0]['finding_hash'][:8]}… (same root cause)",
    )


def _phase_6_freeze(root: Path) -> None:
    res = synth_frozen_scenario(V1_REPO, root)
    print(f"  ack-freeze exit={res.returncode}")
    if res.stderr:
        print(f"  stderr: {res.stderr.strip()}")


def _phase_7_drafts(root: Path) -> None:
    drafts = sorted((root / "reports" / "drafts").glob("*.md"))
    for d in drafts:
        print(f"  reports/drafts/{d.name[:12]}….md  ({d.stat().st_size}B)")


def main() -> None:
    preflight()
    root = setup_tree(V1_REPO)
    paths = config.Paths.from_root(root)

    step(1, "Setup: register demo/proof program + seed 4 findings (queued)")
    _phase_1_setup(paths, root)

    step(2, "F1 path: queued → verified → submitted → resolved_na")
    _phase_2_full_happy_path(paths, root)

    step(3, "F2 path: queued → resolved_info (operator direct-dismiss)")
    _phase_3_direct_dismiss(paths)

    step(4, "F3 path: queued → verified → submitted (awaiting platform)")
    _phase_4_filed_awaiting(paths, root)

    step(5, "F4 path: queued → resolved_dupe (operator marks dupe of F1)")
    _phase_5_resolved_dupe(paths)

    step(6, "Freeze scenario: touch FROZEN → bin/ack-freeze")
    _phase_6_freeze(root)

    step(7, "Drafts on disk")
    _phase_7_drafts(root)

    step(8, "Ledger")
    ledger = dump_ledger(root)
    (root / "PROOF_LEDGER.md").write_text(ledger, encoding="utf-8")
    print(f"  wrote {root / 'PROOF_LEDGER.md'}")
    print()
    print("=" * 70)
    print(ledger)


if __name__ == "__main__":
    main()
