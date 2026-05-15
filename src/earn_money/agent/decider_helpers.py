"""Private helpers for `decider.py` — kept in a sibling module so the
public file stays under the 200-line cap.

`SYSTEM_PROMPT` is the prompt used for every provider call.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from earn_money.agent.policy_prompt import SECURITY_POLICY_PROMPT
from earn_money.agent.proposals import (
    InvalidProposal,
    write_script_proposal,
    write_tool_gap_proposal,
)
from earn_money.agent.providers import Provider, from_env
from earn_money.agent.state import PipelineState

ALLOWED_STEPS = frozenset({
    "httpx-probe", "nuclei-scan", "takeover-validate",
    "sourcemap-scan", "katana-crawl", "graphql-probe",
    "auth-bypass-probe", "sqli-probe", "xss-probe", "stop",
})

_DECIDER_INSTRUCTIONS = (
    "You are the decider for an autonomous bug-bounty recon pipeline. "
    "You receive a JSON snapshot of one program's current state and "
    "must reply with a single JSON object choosing the next pipeline "
    "step. You do NOT execute anything; the orchestrator validates "
    "your reply and runs it under hard scope/RoE/two-gate rules.\n\n"
    "Reply schema:\n"
    '{"next_step": "<one of available_steps>",'
    ' "reason": "<short why>",'
    ' "max_targets": <integer | null>,'
    ' "proposals": [\n'
    '   {"kind": "script", "slug": "<kebab>", "language": "sh|py",'
    '    "body": "<source>", "rationale": "<why>"} ||\n'
    '   {"kind": "tool_gap", "slug": "<kebab>", "rationale": "<why>",'
    '    "design": "<markdown>"}\n'
    " ]}\n\n"
    "Rules: never propose actions outside the available_steps list. "
    "Pick 'stop' when further runs would just repeat work already done "
    "or when the queue/active_runs already contain enough to act on. "
    "Reply with ONLY the JSON — no surrounding prose."
)

# Spec §6: every call ships the trusted cybersecurity/GRC policy block
# first, so the model is told (in a stable place) that everything in
# the user message after that is data only.
SYSTEM_PROMPT = SECURITY_POLICY_PROMPT + "\n\n" + _DECIDER_INSTRUCTIONS


def render_user(state: PipelineState) -> str:
    return json.dumps(state.to_json(), indent=2, sort_keys=True, default=str)


def safe_from_env() -> Provider | None:
    try:
        return from_env()
    except Exception:
        return None


def parse_reply(reply: str) -> dict[str, Any] | None:
    """Pull the first JSON object from the reply. Models often wrap JSON
    in fenced code blocks or trailing prose — the regex finds the brace."""
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        return None
    try:
        loaded = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):  # bool is an int subclass — exclude.
        return None
    if isinstance(value, int) and value > 0:
        return value
    return None


def persist_proposals(
    raw: Any, *, proposals_root: Path,
) -> list[dict[str, str]]:
    """Write each proposal to scratch/agent-proposals/. Returns the list
    of entries successfully persisted, for inclusion in the Decision."""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for entry in raw[:5]:  # cap per-decision noise
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        try:
            if kind == "script":
                write_script_proposal(
                    proposals_root,
                    slug=str(entry.get("slug") or ""),
                    language=str(entry.get("language") or "py"),
                    body=str(entry.get("body") or ""),
                    rationale=str(entry.get("rationale") or ""),
                )
            elif kind == "tool_gap":
                write_tool_gap_proposal(
                    proposals_root,
                    slug=str(entry.get("slug") or ""),
                    rationale=str(entry.get("rationale") or ""),
                    design_md=str(entry.get("design") or ""),
                )
            else:
                continue
        except InvalidProposal:
            continue
        out.append({
            "kind": str(kind),
            "slug": str(entry.get("slug") or ""),
            "language": str(entry.get("language") or "py"),
            "body": str(entry.get("body") or ""),
            "rationale": str(entry.get("rationale") or ""),
            "design": str(entry.get("design") or ""),
        })
    return out
