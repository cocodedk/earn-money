"""Structured session memory for the probe loop.

Separates trusted facts (tokens, IDs, URLs) from guesses (hypotheses,
candidates). prompt_view() never leaks raw token values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from earn_money.agent.observations import ObservationWrapper


@dataclass
class HackerSession:
    tokens: dict[str, str] = field(default_factory=dict)
    ids: dict[str, str] = field(default_factory=dict)
    urls: list[str] = field(default_factory=list)
    observations: list[ObservationWrapper] = field(default_factory=list)
    hypotheses: list[str] = field(default_factory=list)
    candidate_findings: list[dict[str, Any]] = field(default_factory=list)
    verified_findings: list[dict[str, Any]] = field(default_factory=list)
    turn_log: list[str] = field(default_factory=list)
    policy_denials: list[str] = field(default_factory=list)

    # ── mutations ─────────────────────────────────────────────────────────────

    def store_token(self, key: str, value: str) -> None:
        self.tokens[key] = value

    def get_token(self, key: str) -> str | None:
        return self.tokens.get(key)

    def store_id(self, key: str, value: str) -> None:
        self.ids[key] = value

    def seed_urls(self, urls: list[str]) -> None:
        for url in urls:
            if url not in self.urls:
                self.urls.append(url)

    def add_observation(self, obs: ObservationWrapper) -> None:
        self.observations.append(obs)

    def add_hypothesis(self, hypothesis: str) -> None:
        self.hypotheses.append(hypothesis)

    def add_candidate_finding(self, finding: dict[str, Any]) -> None:
        self.candidate_findings.append(finding)

    def add_verified_finding(self, finding: dict[str, Any]) -> None:
        self.verified_findings.append(finding)

    def add_policy_denial(self, reason: str) -> None:
        self.policy_denials.append(reason)

    def log_turn(self, action: dict[str, Any], result: str) -> None:
        self.turn_log.append(f"action={action!r} result={result!r}")

    # ── read-only views ───────────────────────────────────────────────────────

    def summary(self) -> dict[str, int]:
        return {
            "tokens": len(self.tokens),
            "ids": len(self.ids),
            "urls": len(self.urls),
            "observations": len(self.observations),
            "hypotheses": len(self.hypotheses),
            "candidate_findings": len(self.candidate_findings),
            "verified_findings": len(self.verified_findings),
            "turns": len(self.turn_log),
            "policy_denials": len(self.policy_denials),
        }

    def prompt_view(self) -> str:
        lines = [
            f"tokens: {list(self.tokens.keys())}",
            f"ids: {dict(self.ids)}",
            f"urls: {self.urls}",
            f"hypotheses: {self.hypotheses}",
            f"candidate_findings: {len(self.candidate_findings)}",
            f"verified_findings: {len(self.verified_findings)}",
            f"policy_denials: {self.policy_denials}",
            "",
            "--- observations ---",
        ]
        for obs in self.observations[-5:]:  # last 5 only to keep prompt bounded
            lines.append(obs.to_prompt())
        return "\n".join(lines)
