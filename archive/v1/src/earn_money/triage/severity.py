"""Shared severity ranking and sort key for queued findings.

The CLI (`bin/queue`) and the dashboard aggregator must agree on what
"top queued" means. Centralising the ordering rule here is the single
source of truth — change it here, both surfaces stay aligned.
"""

from __future__ import annotations

from earn_money.triage.findings import Finding

SEVERITY_RANK: dict[str, int] = {
    "critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "unknown": 5,
}


def sort_key(finding: Finding) -> tuple[int, str]:
    """Sort key: severity rank ascending (critical first), then first_seen ascending."""
    return (
        SEVERITY_RANK.get(finding.severity_hint, SEVERITY_RANK["unknown"]),
        finding.first_seen,
    )
