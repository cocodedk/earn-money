"""One-shot live test: run the V3 agent against Juice Shop.

Usage:
    ANTHROPIC_API_KEY=sk-... DJANGO_ALLOW_ASYNC_UNSAFE=true python live_test_agent.py
"""
from __future__ import annotations

import asyncio
import os

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


async def main() -> None:
    profile = get_profile("juice_shop_scoreboard")
    project, _ = Project.objects.get_or_create(name="v3-live-test")
    target, _ = ScanTarget.objects.get_or_create(
        host=profile.target, project=project,
    )
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)

    session = create_session(
        scan_run=scan_run,
        target_run=target_run,
        target=target,
        mission_profile=profile.name,
        model_policy=profile.model_policy,
        mission_budget=profile.mission_budget,
    )
    emit_session_started(session)

    api_key = os.environ["ANTHROPIC_API_KEY"]
    model = profile.model_policy.get("primary_model", "claude-sonnet-4-6")
    provider = create_provider(model=model, api_key=api_key, provider_type="anthropic")

    driver = PlaywrightDriver()
    await driver.start(f"https://{profile.target}")

    try:
        controller = MissionController(
            session=session,
            provider=provider,
            driver=driver,
            objective=profile.objective,
            mission_budget=profile.mission_budget,
            phase_budgets=profile.phase_budgets,
            model_name=model,
        )
        session = await controller.run()
        print(f"Mission finished: {session.status}")
        print(f"Phase: {session.current_phase}")
        print(f"Consumed: {session.consumed_budget}")

        from apps.agent.models import AgentNote
        candidates = AgentNote.objects.filter(session=session, note_type="candidate")
        for c in candidates:
            print(f"Candidate: {c.content}")
    finally:
        await driver.stop()


if __name__ == "__main__":
    asyncio.run(main())
