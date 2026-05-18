"""Per-action-type policy for the agent's `proposed_actions[]`.

Spec §10: the model may propose actions, but application code decides
what is allowed. This module is the single source of truth for which
action types the agent is permitted to suggest, what risk tier they
carry, and which require operator approval before execution.

The agent never *executes* anything — proposed actions only land in
the persisted Decision so the operator and the dashboard can see
what the agent thought next. This module's job is to gate which
proposals are valid + which automatically flip `requires_human_review`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RiskLevel = Literal["low", "medium", "high"]
ReviewReason = Literal[
    "ok", "unknown_action", "human_review", "blocked",
]


@dataclass(frozen=True)
class ActionPolicy:
    action_type: str
    risk_level: RiskLevel
    allowed: bool
    requires_human_review: bool


# Allowlist per spec §10. Risk + review flags are policy decisions
# that survive even if the LLM tries to argue otherwise — the agent's
# own `risk_level` / `allowed` claims in the JSON reply are validated
# against THIS table, not trusted from the model.
_ALLOWLIST: dict[str, ActionPolicy] = {
    # Low-risk: pure analysis, the agent's normal day job.
    "classify_finding":        ActionPolicy("classify_finding",        "low",    True,  False),
    "draft_remediation":       ActionPolicy("draft_remediation",       "low",    True,  False),
    "map_finding_to_control":  ActionPolicy("map_finding_to_control",  "low",    True,  False),
    "extract_technology_hint": ActionPolicy("extract_technology_hint", "low",    True,  False),
    "summarize_evidence":      ActionPolicy("summarize_evidence",      "low",    True,  False),
    "suggest_passive_check":   ActionPolicy("suggest_passive_check",   "low",    True,  False),
    "produce_report_text":     ActionPolicy("produce_report_text",     "low",    True,  False),
    "produce_structured_json": ActionPolicy("produce_structured_json", "low",    True,  False),
    # Confirmation-required: needs operator review before execution.
    "severity_downgrade":      ActionPolicy("severity_downgrade",      "medium", True,  True),
    "propose_new_runner":      ActionPolicy("propose_new_runner",      "medium", True,  True),
    "propose_one_off_script":  ActionPolicy("propose_one_off_script",  "medium", True,  True),
    # Blocked outright — operator can never authorize through the agent
    # path. These require explicit operator action via bin/* tools.
    "active_exploitation":     ActionPolicy("active_exploitation",     "high",   False, True),
    "credential_use":          ActionPolicy("credential_use",          "high",   False, True),
    "destructive_payload":     ActionPolicy("destructive_payload",     "high",   False, True),
    "data_exfiltration":       ActionPolicy("data_exfiltration",       "high",   False, True),
    "send_message":            ActionPolicy("send_message",            "high",   False, True),
    "modify_scope":            ActionPolicy("modify_scope",            "high",   False, True),
    "modify_scanner_config":   ActionPolicy("modify_scanner_config",   "high",   False, True),
    "call_arbitrary_url":      ActionPolicy("call_arbitrary_url",      "high",   False, True),
    "shell_command":           ActionPolicy("shell_command",           "high",   False, True),
    "authenticated_request":   ActionPolicy("authenticated_request",   "high",   False, True),
    "delete_finding":          ActionPolicy("delete_finding",          "high",   False, True),
    "suppress_finding":        ActionPolicy("suppress_finding",        "high",   False, True),
    "hide_finding":            ActionPolicy("hide_finding",            "high",   False, True),
}


@dataclass(frozen=True)
class ValidatedAction:
    action_type: str
    risk_level: RiskLevel
    allowed: bool
    requires_human_review: bool
    reason: str


def validate_action(action_type: str) -> ValidatedAction:
    """Look up `action_type` against the allowlist; rejected types
    surface as `allowed=False` + `requires_human_review=True` so the
    operator sees them rather than them being silently dropped."""
    policy = _ALLOWLIST.get(action_type)
    if policy is None:
        return ValidatedAction(
            action_type=action_type,
            risk_level="high",
            allowed=False,
            requires_human_review=True,
            reason="unknown action type — not in allowlist",
        )
    return ValidatedAction(
        action_type=policy.action_type,
        risk_level=policy.risk_level,
        allowed=policy.allowed,
        requires_human_review=policy.requires_human_review,
        reason="ok" if policy.allowed else "blocked by allowlist policy",
    )


def validate_actions(
    proposed: list[dict[str, object]],
) -> list[ValidatedAction]:
    """Vet every entry in the agent's `proposed_actions[]`. Returns a
    parallel list; unknown / malformed entries become unallowed
    high-risk records, not crashes."""
    out: list[ValidatedAction] = []
    for entry in proposed[:20]:  # cap per-decision noise
        action_type = (
            str(entry.get("action_type") or "") if isinstance(entry, dict) else ""
        )
        out.append(validate_action(action_type))
    return out


def any_requires_human_review(validated: list[ValidatedAction]) -> bool:
    """Convenience predicate for `Decision.requires_human_review`."""
    return any(a.requires_human_review for a in validated)
