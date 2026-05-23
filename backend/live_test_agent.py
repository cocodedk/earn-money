"""One-shot live test: run the V3 agent against Juice Shop.

Usage (OpenRouter — default):
    OPENROUTER_API_KEY=sk-or-... python live_test_agent.py

Usage (Anthropic direct):
    ANTHROPIC_API_KEY=sk-... LLM_PROVIDER=anthropic python live_test_agent.py
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

import django

django.setup()

from apps.agent.controller import MissionController
from apps.agent.llm.providers import create_provider
from apps.agent.browser.driver import PlaywrightDriver
from apps.agent.mission_profiles import get_profile
from apps.agent.persistence import create_session
from apps.agent.event_log import emit_session_started
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget
from apps.projects.models import Project

OPENROUTER_KEY_PATH = Path.home() / ".config/openclaw/openrouter_api_key"


def _resolve_provider() -> tuple[str, str, str]:
    provider_type = os.environ.get("LLM_PROVIDER", "openrouter")
    if provider_type == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key and OPENROUTER_KEY_PATH.exists():
            api_key = OPENROUTER_KEY_PATH.read_text().strip()
        model = os.environ.get("LLM_MODEL", "anthropic/claude-sonnet-4-6")
        return provider_type, model, api_key
    api_key = os.environ["ANTHROPIC_API_KEY"]
    model = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
    return provider_type, model, api_key


async def main() -> None:
    profile = get_profile("juice_shop_scoreboard")
    project, _ = Project.objects.get_or_create(name="v3-live-test")
    target, _ = ScanTarget.objects.get_or_create(
        host=profile.target, project=project,
    )
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)

    session = create_session(
        scan_run=scan_run, target_run=target_run, target=target,
        mission_profile=profile.name, model_policy=profile.model_policy,
        mission_budget=profile.mission_budget,
    )
    emit_session_started(session)

    provider_type, model, api_key = _resolve_provider()
    print(f"Provider: {provider_type}, Model: {model}")
    provider = create_provider(model=model, api_key=api_key, provider_type=provider_type)

    driver = PlaywrightDriver()
    await driver.start(f"https://{profile.target}")

    try:
        controller = MissionController(
            session=session, provider=provider, driver=driver,
            objective=profile.objective, mission_budget=profile.mission_budget,
            phase_budgets=profile.phase_budgets, model_name=model,
        )
        session = await controller.run()
        print(f"Mission finished: {session.status}")
        print(f"Phase: {session.current_phase}")
        print(f"Consumed: {session.consumed_budget}")

        from apps.agent.models import AgentNote
        for c in AgentNote.objects.filter(session=session, note_type="candidate"):
            print(f"Candidate: {c.content}")
    finally:
        await driver.stop()


if __name__ == "__main__":
    asyncio.run(main())
