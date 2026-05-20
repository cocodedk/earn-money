"""Pure file-writing helpers for the nuclei-scan runner. Extracted to
keep `nuclei_scan.py` under the 200-line cap. Callers: nuclei_scan
itself and `_prereq.record_prereq_missing` (which takes these as
injected callables so each runner can keep its own filename conventions).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from earn_money.recon.signals import Signal


def write_manifest(artifact_dir: Path, payload: dict[str, Any]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def write_signals_jsonl(artifact_dir: Path, sigs: list[Signal]) -> None:
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


def write_required_artifacts(
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
