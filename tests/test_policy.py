from __future__ import annotations

import pytest

from earn_money import policy, scope


def _scope(p: scope.Policy) -> scope.Scope:
    return scope.Scope(
        platform="hackerone", slug="example", policy=p,
        in_scope=[], out_of_scope=[], notes="",
        scope_hash="", last_synced="",
    )


def test_rate_limited_allows_both_modes() -> None:
    s = _scope("rate-limited-OK")
    policy.require_policy_allows(s, mode="passive")
    policy.require_policy_allows(s, mode="active")


def test_manual_only_refuses_both() -> None:
    s = _scope("manual-only")
    with pytest.raises(policy.PolicyViolation):
        policy.require_policy_allows(s, mode="passive")
    with pytest.raises(policy.PolicyViolation):
        policy.require_policy_allows(s, mode="active")


def test_ambiguous_allows_passive() -> None:
    s = _scope("ambiguous")
    policy.require_policy_allows(s, mode="passive")  # no raise


@pytest.mark.parametrize(
    "policy_value, mode",
    [
        ("manual-only", "passive"),
        ("manual-only", "active"),
        ("ambiguous", "active"),
    ],
)
def test_violation_message_names_policy_and_mode(
    policy_value: scope.Policy, mode: policy.Mode
) -> None:
    s = _scope(policy_value)
    with pytest.raises(policy.PolicyViolation) as excinfo:
        policy.require_policy_allows(s, mode=mode)
    assert policy_value in str(excinfo.value)
    assert mode in str(excinfo.value)
