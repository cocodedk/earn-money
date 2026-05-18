"""Central UTC-now helper.

datetime.now(UTC).isoformat() emits '+00:00', but the project convention
(test fixtures, shell audit logs in freeze-acks.log, scope.md headers)
uses the shorter 'Z' suffix. One helper, one format — so audit history,
recon run logs, and operator-edited markdown all sort and compare cleanly.
"""

from __future__ import annotations

from datetime import UTC, datetime


def to_iso(dt: datetime) -> str:
    """Format a UTC datetime as 'YYYY-MM-DDTHH:MM:SSZ'."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def now_iso() -> str:
    """Current UTC timestamp as 'YYYY-MM-DDTHH:MM:SSZ'."""
    return to_iso(datetime.now(UTC))
