---
tier: APEX
depends_on:
  - 08-page-observation
  - 09-asset-observation
files:
  creates:
    - backend/apps/agent/observations/builder.py
    - backend/apps/agent/tests/test_builder.py
  modifies: []
allow_extra_files: false
---

### Task 10: Observation builder (Playwright → PageObservation)

**Files:**
- Create: `backend/apps/agent/observations/builder.py`
- Create: `backend/apps/agent/tests/test_builder.py`

This task builds the bridge from raw Playwright page state to the normalized
PageObservation. In tests we mock the Playwright page object — real Playwright
tests come in Task 11 (browser driver) and Task 19 (integration).

- [ ] **Step 1: Write tests with mocked Playwright page**

```python
# backend/apps/agent/tests/test_builder.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from apps.agent.observations.builder import ObservationBuilder


@pytest.fixture
def mock_page():
    page = AsyncMock()
    page.url = "https://juiceshop.cocode.dk/"
    page.title = AsyncMock(return_value="OWASP Juice Shop")

    snapshot = {
        "role": "WebArea",
        "name": "OWASP Juice Shop",
        "children": [
            {"role": "link", "name": "About Us", "url": "/about"},
            {"role": "button", "name": "Login", "disabled": False},
        ],
    }
    page.accessibility.snapshot = AsyncMock(return_value=snapshot)
    page.context.cookies = AsyncMock(return_value=[
        {"name": "session", "domain": "juiceshop.cocode.dk", "path": "/",
         "secure": True, "httpOnly": True, "sameSite": "Lax", "value": "secret123"},
    ])
    page.evaluate = AsyncMock(return_value=[])
    return page


@pytest.mark.asyncio
async def test_builder_produces_page_observation(mock_page):
    builder = ObservationBuilder(target_origin="juiceshop.cocode.dk")
    obs = await builder.build_page_observation(
        page=mock_page, turn=0, phase="recon", action_ref="act_0",
        network_entries=[],
    )
    assert obs.page.path == "/"
    assert obs.page.title == "OWASP Juice Shop"


@pytest.mark.asyncio
async def test_builder_strips_cookie_values(mock_page):
    builder = ObservationBuilder(target_origin="juiceshop.cocode.dk")
    obs = await builder.build_page_observation(
        page=mock_page, turn=0, phase="recon", action_ref="act_0",
        network_entries=[],
    )
    d = obs.to_dict()
    for cookie in d["browser_state"]["cookies"]:
        assert "value" not in cookie


@pytest.mark.asyncio
async def test_builder_assigns_controller_ids(mock_page):
    builder = ObservationBuilder(target_origin="juiceshop.cocode.dk")
    obs = await builder.build_page_observation(
        page=mock_page, turn=0, phase="recon", action_ref="act_0",
        network_entries=[],
    )
    d = obs.to_dict()
    for link in d["elements"]["links"]:
        assert link["id"].startswith("link_")
    for btn in d["elements"]["buttons"]:
        assert btn["id"].startswith("btn_")


@pytest.mark.asyncio
async def test_builder_resolves_asset_refs(mock_page):
    builder = ObservationBuilder(target_origin="juiceshop.cocode.dk")
    obs = await builder.build_page_observation(
        page=mock_page, turn=0, phase="recon", action_ref="act_0",
        network_entries=[
            {"url": "https://juiceshop.cocode.dk/main.js", "resource_type": "script"},
        ],
    )
    asset = obs.discovered.assets[0]
    assert builder.resolve_asset_ref(asset.id) == "/main.js"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_builder.py -v`
Expected: FAIL


See [10-observation-builder-impl.md](10-observation-builder-impl.md) for Step 3 implementation code.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_builder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/observations/builder.py backend/apps/agent/tests/test_builder.py
git commit -m "feat(agent): add ObservationBuilder (Playwright → PageObservation)"
```
