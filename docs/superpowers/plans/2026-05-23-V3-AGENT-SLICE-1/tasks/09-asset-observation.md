---
tier: CAPABLE
depends_on:
  - 08-page-observation
files:
  creates:
    - backend/apps/agent/observations/assets.py
    - backend/apps/agent/tests/test_asset_observation.py
  modifies: []
allow_extra_files: false
---

### Task 9: AssetObservation dataclass

**Files:**
- Create: `backend/apps/agent/observations/assets.py`
- Create: `backend/apps/agent/tests/test_asset_observation.py`

- [ ] **Step 1: Write tests**

```python
# backend/apps/agent/tests/test_asset_observation.py
from apps.agent.observations.assets import AssetObservation, AssetExcerpt


def test_asset_observation_to_dict():
    obs = AssetObservation(
        asset_ref="asset_2", path="/main.js", type="script",
        size_bytes=142000, truncated=True,
        excerpts=[
            AssetExcerpt(
                context="route definition", match="/score-board",
                surrounding="path: '/score-board', component: ScoreBoardComponent",
            ),
        ],
        strings_of_interest=["/score-board", "/api/Users"],
    )
    d = obs.to_dict()
    assert d["trust"] == "untrusted_target_content"
    assert d["excerpts"][0]["match"] == "/score-board"
    assert "/score-board" in d["strings_of_interest"]


def test_asset_observation_empty_excerpts():
    obs = AssetObservation(
        asset_ref="asset_1", path="/vendor.js", type="script",
        size_bytes=500000, truncated=True,
        excerpts=[], strings_of_interest=[],
    )
    d = obs.to_dict()
    assert d["excerpts"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest apps/agent/tests/test_asset_observation.py -v`
Expected: FAIL

- [ ] **Step 3: Implement AssetObservation**

```python
# backend/apps/agent/observations/assets.py
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class AssetExcerpt:
    context: str
    match: str
    surrounding: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AssetObservation:
    asset_ref: str
    path: str
    type: str
    size_bytes: int
    truncated: bool
    excerpts: list[AssetExcerpt]
    strings_of_interest: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset_ref": self.asset_ref,
            "path": self.path,
            "type": self.type,
            "trust": "untrusted_target_content",
            "size_bytes": self.size_bytes,
            "truncated": self.truncated,
            "excerpts": [e.to_dict() for e in self.excerpts],
            "strings_of_interest": list(self.strings_of_interest),
        }
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest apps/agent/tests/test_asset_observation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/apps/agent/observations/assets.py backend/apps/agent/tests/test_asset_observation.py
git commit -m "feat(agent): add AssetObservation dataclass"
```
