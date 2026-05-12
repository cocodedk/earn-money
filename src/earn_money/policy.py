"""Policy-tier enforcement for recon runners."""

from __future__ import annotations

from typing import Literal

from earn_money.scope import Scope

Mode = Literal["passive", "active"]


class PolicyViolation(Exception):
    """Raised when the requested mode is not permitted by the program's policy."""


def require_policy_allows(scope: Scope, *, mode: Mode) -> None:
    if scope.policy == "rate-limited-OK":
        return
    if scope.policy == "ambiguous" and mode == "passive":
        return
    raise PolicyViolation(
        f"Program {scope.platform}/{scope.slug} has policy={scope.policy!r}; "
        f"mode={mode!r} is not permitted. "
        "Operator must scan this program manually or escalate scope tier."
    )
