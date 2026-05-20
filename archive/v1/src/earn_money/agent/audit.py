"""Append-only audit log for agent LLM calls (spec §13).

One JSONL file per UTC date under `<root>/scratch/agent-audit/`.
Every recorded event passes through a redactor that strips obvious
secrets before they hit disk — API keys, bearer tokens, cookies. We
never log full sensitive payloads; only the metadata operators need
to reconstruct *what the agent did and why*.

Logged per spec §13:
- evidence_id, evidence_source, content_hash
- injection-detector result + matched indicators
- model profile (task type), model_id (when known)
- prompt_template_version, schema_version
- proposed_actions + validated outcomes
- validation errors
- final finding_id when the chain terminates in one

NOT logged: API keys / tokens / cookies / credentials / sensitive
payloads. Any value that looks key-shaped gets redacted to its first
four chars + ellipsis.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Match the obvious secret-shaped strings. Order matters — most-specific
# first so partial matches don't pre-empt the right redaction.
_REDACTORS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"), "sk-ant-…"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "sk-…"),       # OpenAI style
    (re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"), "hf_…"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._-]{12,}", re.IGNORECASE), "Bearer …"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AKIA…"),
    (re.compile(r"\bgh[opusr]_[A-Za-z0-9]{36,}\b"), "gh*_…"),
    (re.compile(r"\bxox[bpoasrlt]-[0-9A-Za-z-]{20,}\b"), "xox…"),
    (re.compile(r"(Cookie:|Set-Cookie:|Authorization:)\s+\S+", re.IGNORECASE),
     r"\1 [REDACTED]"),
)


@dataclass(frozen=True)
class AuditEvent:
    """One row in the audit log. Keys are stable across versions."""
    event_type: str               # "agent_decision" | "structured_call" | "evidence_wrap"
    platform: str
    slug: str
    timestamp: str                # ISO 8601 UTC
    task: str | None = None
    model_id: str | None = None
    prompt_template_version: str | None = None
    schema_version: str | None = None
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    injection_indicators: tuple[str, ...] = field(default_factory=tuple)
    proposed_actions: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    validation_errors: tuple[str, ...] = field(default_factory=tuple)
    requires_human_review: bool = False
    finding_id: str | None = None


def record(audit_root: Path, event: AuditEvent) -> Path:
    """Append `event` to the per-day audit JSONL file. Returns the path."""
    audit_root.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    target = audit_root / f"{today}.jsonl"
    payload = redact(asdict(event))
    with target.open("a", encoding="utf-8") as fh:
        # ensure_ascii=False keeps the file human-readable + lets the
        # redaction markers (which use U+2026 …) survive a grep.
        fh.write(json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False))
        fh.write("\n")
    return target


def redact(value: Any) -> Any:
    """Recursively walk strings/dicts/lists and replace key-shaped
    matches with a short marker. Pure; safe to call before logging."""
    if isinstance(value, str):
        return _redact_str(value)
    if isinstance(value, Mapping):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        out = [redact(v) for v in value]
        return tuple(out) if isinstance(value, tuple) else out
    return value


def _redact_str(value: str) -> str:
    out = value
    for pattern, repl in _REDACTORS:
        out = pattern.sub(repl, out)
    return out


def audit_root_for(repo_root: Path) -> Path:
    """Canonical location for the agent audit log inside a repo root."""
    return repo_root / "scratch" / "agent-audit"
