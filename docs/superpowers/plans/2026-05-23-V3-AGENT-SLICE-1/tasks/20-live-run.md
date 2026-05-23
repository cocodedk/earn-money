### Task 20: Live Juice Shop run (manual verification)

**Files:** No new files — this is a manual verification step.

This task runs the agent against the real Juice Shop at
`juiceshop.cocode.dk`. It requires a real LLM API key and Playwright
installed. Run only after all unit/integration tests pass.

- [ ] **Step 1: Create a runner script**

```python
# backend/live_test_agent.py
"""One-shot live test: run the V3 agent against Juice Shop.

Usage:
    ANTHROPIC_API_KEY=sk-... python live_test_agent.py
"""
import asyncio
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.agent.controller import MissionController
from apps.agent.llm.providers import create_provider
from apps.agent.browser.driver import PlaywrightDriver
from apps.agent.mission_profiles import get_profile
from apps.scans.models import ScanRun, ScanTargetRun
from apps.targets.models import ScanTarget
from apps.projects.models import Project


async def main():
    profile = get_profile("juice_shop_scoreboard")
    project, _ = Project.objects.get_or_create(name="v3-live-test")
    target, _ = ScanTarget.objects.get_or_create(
        host=profile.target, project=project,
    )
    scan_run = ScanRun.objects.create(project=project, stub_slug="agent.v3")
    target_run = ScanTargetRun.objects.create(scan_run=scan_run, target=target)

    provider = create_provider(
        model="claude-sonnet-4-6",
        api_key=os.environ["ANTHROPIC_API_KEY"],
        provider_type="anthropic",
    )
    driver = PlaywrightDriver()
    await driver.start(f"https://{profile.target}")

    try:
        controller = MissionController(
            provider=provider, driver=driver,
            scan_run=scan_run, target_run=target_run, target=target,
            mission_profile=profile.name,
            mission_budget=profile.mission_budget,
            phase_budgets=profile.phase_budgets,
            objective=profile.objective,
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
```

- [ ] **Step 2: Run against live Juice Shop**

Run: `cd backend && ANTHROPIC_API_KEY=sk-... python live_test_agent.py`

Expected: Agent discovers `/score-board` or `/#/score-board` route, submits a
candidate with category `hidden_route_discovered`, and completes within budget.

- [ ] **Step 3: Verify acceptance criteria**

Check that:
1. Agent observed the page and discovered JS assets
2. Agent inspected a JS bundle and found a route containing "score-board"
3. Agent navigated to the scoreboard view
4. A candidate note with `hidden_route_discovered` was persisted
5. All turns have artifact refs and token counts
6. Mission completed within budget

- [ ] **Step 4: Commit runner script**

```bash
git add backend/live_test_agent.py
git commit -m "test(agent): add live Juice Shop runner script"
```
