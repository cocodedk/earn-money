from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MissionProfile:
    """Immutable configuration for a named agent mission."""

    name: str
    target: str
    objective: str
    success_category: str
    phases: list[str]
    mission_budget: dict
    phase_budgets: dict
    model_policy: dict


_PROFILES: dict[str, MissionProfile] = {
    "juice_shop_scoreboard": MissionProfile(
        name="juice_shop_scoreboard",
        target="juiceshop.cocode.dk",
        objective=(
            "Discover and access the hidden scoreboard page at "
            "/#!/score-board on OWASP Juice Shop."
        ),
        success_category="security_misconfiguration",
        phases=["recon", "enumerate", "report"],
        mission_budget={
            "max_turns": 25,
            "max_runtime_seconds": 300,
            "max_llm_calls": 30,
            "max_http_requests": 60,
            "max_browser_actions": 40,
            "max_asset_inspections": 10,
        },
        phase_budgets={
            "recon": {
                "max_turns": 8,
                "max_browser_actions": 15,
                "max_http_requests": 20,
            },
            "enumerate": {
                "max_turns": 12,
                "max_browser_actions": 20,
                "max_http_requests": 30,
            },
            "report": {
                "max_turns": 5,
                "max_browser_actions": 5,
                "max_http_requests": 10,
            },
        },
        model_policy={
            "provider": "openrouter",
            "model": "deepseek/deepseek-v4-pro",
            "reasoning": {"effort": "high"},
        },
    ),
}


def get_profile(name: str) -> MissionProfile:
    """Return the named MissionProfile, raising KeyError if not found."""
    try:
        return _PROFILES[name]
    except KeyError:
        available = sorted(_PROFILES)
        raise KeyError(
            f"Unknown mission profile {name!r}. Available: {available}"
        ) from None
