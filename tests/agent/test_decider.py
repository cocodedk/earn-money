"""Tests for the agent decider — mocked Provider, no network."""

from __future__ import annotations

import json
from pathlib import Path

from earn_money import config, scope
from earn_money.agent.decider import Decision, decide_next_step
from earn_money.agent.providers import Provider


def _seed_scope(paths: config.Paths) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["api.example.com"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


class _StubProvider:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.reply


class _BoomProvider:
    def complete(self, *, system: str, user: str) -> str:
        raise RuntimeError("api down")


def test_happy_path_returns_chosen_step(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    provider: Provider = _StubProvider(json.dumps({  # type: ignore[assignment]
        "next_step": "takeover-validate",
        "reason": "no recent takeover signals; high-payout class",
        "max_targets": 50,
        "proposals": [],
    }))
    decision = decide_next_step(
        paths, "hackerone", "example", provider=provider,
    )
    assert decision.next_step == "takeover-validate"
    assert decision.max_targets == 50
    assert decision.provider_error is None
    assert decision.proposals == ()


def test_falls_back_when_provider_raises(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    provider: Provider = _BoomProvider()  # type: ignore[assignment]
    decision = decide_next_step(
        paths, "hackerone", "example", provider=provider,
    )
    assert decision.next_step == "httpx-probe"  # first un-completed step
    assert "api down" in (decision.provider_error or "")


def test_falls_back_when_reply_is_not_json(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    provider: Provider = _StubProvider("nope just prose no json here")  # type: ignore[assignment]
    decision = decide_next_step(
        paths, "hackerone", "example", provider=provider,
    )
    assert decision.next_step == "httpx-probe"
    assert "could not parse" in (decision.provider_error or "")


def test_falls_back_when_next_step_unknown(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    provider: Provider = _StubProvider(json.dumps({"next_step": "rm -rf /"}))  # type: ignore[assignment]
    decision = decide_next_step(
        paths, "hackerone", "example", provider=provider,
    )
    assert decision.next_step == "httpx-probe"
    assert "unknown step" in (decision.provider_error or "")


def test_persists_proposals_to_scratch(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    reply = json.dumps({
        "next_step": "stop",
        "reason": "writing a custom probe instead",
        "proposals": [
            {
                "kind": "script", "slug": "probe-cors",
                "language": "sh", "body": "curl -I https://api.example.com\n",
                "rationale": "verify CORS reflection",
            },
            {
                "kind": "tool_gap", "slug": "ffuf-wrapper",
                "rationale": "need endpoint fuzzing once katana surfaces routes",
                "design": "## design\nwrap ffuf with scope-aware target loader",
            },
            # Bad slug — should be silently dropped, not crash the decision.
            {"kind": "script", "slug": "../etc/passwd",
             "language": "sh", "body": "x", "rationale": "x"},
        ],
    })
    provider: Provider = _StubProvider(reply)  # type: ignore[assignment]
    decision: Decision = decide_next_step(
        paths, "hackerone", "example", provider=provider,
    )
    assert decision.next_step == "stop"
    assert len(decision.proposals) == 2
    kinds = {p.kind for p in decision.proposals}
    assert kinds == {"script", "tool_gap"}

    scripts_dir = paths.root / "scratch/agent-proposals/scripts"
    gaps_dir = paths.root / "scratch/agent-proposals/tool-gaps"
    assert any("probe-cors" in p.name for p in scripts_dir.iterdir())
    assert any("ffuf-wrapper" in p.name for p in gaps_dir.iterdir())


def test_max_targets_coerced_to_positive_int(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)
    for bad in (0, -5, "twelve", True, False, None, 3.5):
        provider: Provider = _StubProvider(json.dumps({  # type: ignore[assignment]
            "next_step": "stop", "max_targets": bad,
        }))
        d = decide_next_step(paths, "hackerone", "example", provider=provider)
        assert d.max_targets is None, f"failed for {bad!r}: {d.max_targets}"

    provider2: Provider = _StubProvider(json.dumps({  # type: ignore[assignment]
        "next_step": "stop", "max_targets": 25,
    }))
    d2 = decide_next_step(paths, "hackerone", "example", provider=provider2)
    assert d2.max_targets == 25
