"""Triage suppression rules: data-driven routing for known-noise nuclei
templates. Findings matching a rule are routed to _resolved/info/ with a
structured audit trail instead of reaching _queue/.

The matcher is a pure function — no DB, no IO. The loader reads a YAML
file from disk; callers pass the path explicitly so tests can use a
temp-dir fixture without touching the repo-root file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Rule:
    name: str
    vuln_class: str
    severity: str
    reason: str


_REQUIRED_FIELDS = ("name", "vuln_class", "severity", "reason")


def load_rules(path: Path) -> list[Rule]:
    """Parse a YAML rules file into a list of Rule objects.

    Tolerates a missing file by returning an empty list — fresh checkouts
    without triage_rules.yaml run with zero suppression rules, which is
    the engine's default-permissive behaviour.

    Raises ``ValueError`` (with the file path) on malformed YAML, a
    non-mapping top-level, or any rule entry that isn't a mapping with all
    four required fields. The engine runs this on every invocation, so a
    silent skip would hide operator config bugs from view.
    """
    if not path.exists():
        return []
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: malformed YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level must be a mapping, got {type(raw).__name__}")
    items = raw.get("rules", []) or []
    if not isinstance(items, list):
        raise ValueError(f"{path}: 'rules' must be a list, got {type(items).__name__}")
    result: list[Rule] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(
                f"{path}: rules[{idx}] must be a mapping, got {type(item).__name__}"
            )
        missing = [f for f in _REQUIRED_FIELDS if f not in item]
        if missing:
            raise ValueError(
                f"{path}: rules[{idx}] missing required field(s): {', '.join(missing)}"
            )
        result.append(
            Rule(
                name=str(item["name"]),
                vuln_class=str(item["vuln_class"]),
                severity=str(item["severity"]),
                reason=str(item["reason"]),
            )
        )
    return result


def match(rs: list[Rule], *, vuln_class: str, severity: str) -> Rule | None:
    """Return the first rule matching both vuln_class and severity, else None.

    Matching is case-sensitive on both fields. Callers normalize the inputs;
    ``classify()`` already lowercases vuln_class and severity for nuclei
    template matches.
    """
    for r in rs:
        if r.vuln_class == vuln_class and r.severity == severity:
            return r
    return None
