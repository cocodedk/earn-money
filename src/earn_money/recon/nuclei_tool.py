"""Subprocess wrapper around the ProjectDiscovery `nuclei` CLI.

This wrapper is the safety boundary for nuclei. It refuses to build a
command that includes unapproved template directories (DoS, fuzzing,
DAST, paid templates), and it forces the safety flags on every
invocation (`-disable-redirects`, `-no-interactsh`,
`-disable-update-check`).

Template directories are passed as `-t <name>`. nuclei resolves them
against its local template root (~/.nuclei-templates on the VPS).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from earn_money.recon.signals import Signal
from earn_money.triage import hashing

# Template paths are relative to the local templates root
# (~/nuclei-templates on the VPS). nuclei v3+ groups templates under
# protocol directories (http/, network/, code/, …) — we only allow the
# HTTP protocol subset of cves + misconfiguration. Adding more requires
# a deliberate code-review event.
APPROVED_TEMPLATE_DIRS: frozenset[str] = frozenset({
    "http/cves",
    "http/misconfiguration",
})


class UnsafeTemplateProfile(Exception):
    """Raised when build_command is asked to use an unapproved template dir."""


def build_command(
    targets: Sequence[str], *, template_dirs: Sequence[str],
) -> list[str]:
    if not targets:
        raise ValueError("build_command requires at least one target")
    unapproved = set(template_dirs) - APPROVED_TEMPLATE_DIRS
    if unapproved:
        raise UnsafeTemplateProfile(
            f"refusing to invoke nuclei with unapproved template "
            f"directories: {sorted(unapproved)}. "
            f"Approved: {sorted(APPROVED_TEMPLATE_DIRS)}"
        )
    argv: list[str] = [
        "nuclei",
        "-u", ",".join(targets),
        "-jsonl",
        "-silent",
        "-no-color",
        "-disable-redirects",
        "-no-interactsh",
        "-disable-update-check",
        "-rl", "10",
        "-c", "10",
        "-bs", "10",
        "-stats-interval", "60",
    ]
    for d in template_dirs:
        argv.extend(["-t", d])
    return argv


def parse_jsonl(
    raw: str, *, run_id: str, observed_at: str
) -> list[Signal]:
    out: list[Signal] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            out.append(_to_signal(data, run_id=run_id, observed_at=observed_at))
        except (KeyError, ValueError):
            continue
    return out


def _to_signal(
    data: dict[str, Any], *, run_id: str, observed_at: str
) -> Signal:
    template_id = str(data["template-id"])
    matcher_name = data.get("matcher-name") or None
    matched_at = str(data.get("matched-at") or data.get("host") or "")
    extracted_list = data.get("extracted-results") or []
    extracted = extracted_list[0] if extracted_list else None
    info = data.get("info") or {}
    severity = str(info.get("severity") or "unknown")
    name = str(info.get("name") or template_id)

    asset = hashing.normalize_asset(matched_at)
    target = hashing.normalize_target(matched_at)
    signature = hashing.signature_for_nuclei(
        template_id=template_id, matcher_name=matcher_name, extracted=extracted,
    )
    payload = json.dumps({
        "template_id": template_id,
        "matcher_name": matcher_name,
        "matched_at": matched_at,
        "severity": severity,
        "name": name,
        "extracted": extracted,
    }, sort_keys=True)

    return Signal(
        run_id=run_id, tool="nuclei", signal_type="template_match",
        asset=asset, target=target, signature=signature,
        payload=payload, observed_at=observed_at,
    )
