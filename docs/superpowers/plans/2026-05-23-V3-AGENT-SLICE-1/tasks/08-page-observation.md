### Task 8: PageObservation dataclass

**Files:**
- Create: `backend/apps/agent/observations/__init__.py`
- Create: `backend/apps/agent/observations/page.py`
- Create: `backend/apps/agent/tests/test_page_observation.py`

- [ ] **Step 1: Write tests for PageObservation**

```python
# backend/apps/agent/tests/test_page_observation.py
import pytest
from apps.agent.observations.page import (
    PageObservation, PageIdentity, LinkElement, ButtonElement,
    FormElement, FormField, InputElement, VisibleTextBlock,
    DiscoveredRoute, DiscoveredAsset, HtmlExcerpt,
    NetworkEntry, CookieInfo, StorageKey, ConsoleMessage,
    ScreenshotRef, ObservationMeta, Elements, DiscoveredItems,
)


def test_page_observation_to_dict():
    obs = PageObservation(
        id="obs_1", turn=0, phase="recon", action_ref="act_0",
        page=PageIdentity(
            url_ref="url_1", path="/", title="Juice Shop",
            origin_label="target", load_state="networkidle", page_hash="abc",
        ),
        elements=Elements(links=[], buttons=[], forms=[], inputs=[]),
        visible_text=[],
        discovered=DiscoveredItems(routes=[], assets=[]),
        selected_html_excerpts=[],
        network=[],
        cookies=[], storage_keys=[],
        console=[],
        screenshot=ScreenshotRef(artifact_ref=None, reason=None),
        meta=ObservationMeta(
            observed_at="2026-05-23T12:00:00Z",
            response_bytes=5000, truncated=False, redactions=[],
        ),
    )
    d = obs.to_dict()
    assert d["page"]["path"] == "/"
    assert d["id"] == "obs_1"


def test_page_observation_elements():
    link = LinkElement(
        id="link_1", text="About", accessible_name="About",
        href_ref="url_2", visible=True,
    )
    btn = ButtonElement(
        id="btn_1", text="Login", aria_role="button",
        accessible_name="Login", enabled=True,
    )
    form = FormElement(
        id="form_1", method="POST", action_ref="url_3",
        fields=[FormField(id="f_1", label="Email", type="email", required=True)],
    )
    inp = InputElement(
        id="inp_1", label="Search", type="text",
        required=False, value_state="empty",
    )
    elems = Elements(links=[link], buttons=[btn], forms=[form], inputs=[inp])
    d = elems.to_dict()
    assert len(d["links"]) == 1
    assert d["forms"][0]["fields"][0]["label"] == "Email"


def test_trust_annotations():
    obs = PageObservation(
        id="obs_2", turn=1, phase="recon", action_ref="act_1",
        page=PageIdentity(
            url_ref="url_1", path="/", title="Test",
            origin_label="target", load_state="networkidle", page_hash="x",
        ),
        elements=Elements(links=[], buttons=[], forms=[], inputs=[]),
        visible_text=[VisibleTextBlock(id="txt_1", text="Hello", role_context="heading")],
        discovered=DiscoveredItems(routes=[], assets=[
            DiscoveredAsset(
                id="asset_1", path="/main.js", type="script",
                interesting_refs=["/admin"],
            ),
        ]),
        selected_html_excerpts=[], network=[], cookies=[], storage_keys=[],
        console=[ConsoleMessage(level="error", text="fail", source_ref="r1")],
        screenshot=ScreenshotRef(artifact_ref=None, reason=None),
        meta=ObservationMeta(
            observed_at="2026-05-23T12:00:00Z",
            response_bytes=0, truncated=False, redactions=[],
        ),
    )
    d = obs.to_dict()
    assert d["visible_text"]["trust"] == "untrusted_target_content"
    assert d["discovered"]["assets"][0]["trust"] == "untrusted_target_content"
    assert d["console"]["trust"] == "untrusted_target_content"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_page_observation.py -v`
Expected: FAIL


Step 3 implementation code is split across two files:
- [08-page-observation-elements.md](08-page-observation-elements.md) — element dataclasses
- [08-page-observation-composite.md](08-page-observation-composite.md) — composite types + PageObservation

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_page_observation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/observations/ backend/apps/agent/tests/test_page_observation.py
git commit -m "feat(agent): add PageObservation dataclass with trust annotations"
```
