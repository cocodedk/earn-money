# Task 4 — `ProbeRunner` (the dashboard's threaded `HackerLoop` subclass)

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/05-probe-runner.md` (full)

**Files:**
- Create: `src/earn_money/dashboard/probe_runner.py`
- Create: `tests/dashboard/test_probe_runner.py`

The runner inherits `HackerLoop`, overrides the six hooks added in Task 3 to push structured events onto a `queue.Queue`, picks the task per turn, manages the loop thread, and clears the server's slot via the `on_finished` callback.

Target: ≤200 lines. If approaching the cap, split helpers into `probe_runner_events.py` / `probe_runner_select.py` per the spec.

- [ ] **Step 1: Create the test file scaffold + first `_pick_task` test**

Create `tests/dashboard/test_probe_runner.py`:

```python
"""Tests for ProbeRunner — the dashboard's threaded HackerLoop subclass."""
from __future__ import annotations

from unittest.mock import MagicMock

from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType


def _profile(**kwargs: object) -> RoeProfile:
    defaults = dict(
        name="test", source_type=RoeSourceType.MANUAL,
        allowed_hosts=["target.example.com"],
        max_requests=100, max_posts=20, max_turns=10,
        max_runtime_seconds=60, max_response_bytes=5000,
        delay_between_requests_ms=0,
        allow_get=True, allow_post=True, allow_idor_checks=True,
    )
    defaults.update(kwargs)
    return RoeProfile(**defaults)  # type: ignore[arg-type]


def _runner_with_session(observations: list[ObservationWrapper] | None = None):
    """Build a ProbeRunner without actually starting its thread."""
    from earn_money.dashboard.probe_runner import ProbeRunner

    # Construct via factory that bypasses provider env (patched).
    runner = MagicMock(spec=ProbeRunner)
    runner._next_task_hint = None
    runner.session = MagicMock()
    runner.session.observations = observations or []
    # Bind the real _pick_task method to the mock.
    runner._pick_task = ProbeRunner._pick_task.__get__(runner, ProbeRunner)
    return runner


class TestPickTask:
    def test_no_observations_picks_agent_planning(self):
        r = _runner_with_session([])
        assert r._pick_task() == TaskType.AGENT_PLANNING
```

- [ ] **Step 2: Run — expect FAIL (ImportError: probe_runner not found)**

```bash
uv run pytest tests/dashboard/test_probe_runner.py -v
```

- [ ] **Step 3: Create the `ProbeRunner` skeleton with `_pick_task`**

Create `src/earn_money/dashboard/probe_runner.py`:

```python
"""ProbeRunner — the dashboard's threaded HackerLoop subclass.

Overrides the six observation hooks added to `HackerLoop` and pushes
structured events onto a `queue.Queue`. Selects a per-turn task profile
from observation/action context, manages the loop thread, and clears
the server's slot via an `on_finished` callback so there's no circular
import.
"""
from __future__ import annotations

import logging
import queue
import threading
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from earn_money import config
from earn_money.agent import providers as providers_mod
from earn_money.agent.budget import RequestBudget
from earn_money.agent.finding_verifier import FindingVerifier
from earn_money.agent.hacker_loop import HackerLoop, _SYSTEM_PROMPT
from earn_money.agent.hacker_session import HackerSession
from earn_money.agent.http_tool import HttpTool
from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.probe_actions import ReportCandidateAction
from earn_money.agent.roe_policy import RoePolicy
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType, load_roe_profile
from earn_money.agent.scope_policy import ScopePolicy
from earn_money.agent.task_router import RouterUnconfigured, TaskType, resolve_model

log = logging.getLogger(__name__)


class AlreadyRunning(Exception):
    pass


class _StopRequested(Exception):
    """Internal: raised to break out of the loop on operator-cancel."""


class ProbeRunner(HackerLoop):
    def __init__(
        self,
        *,
        base_url: str,
        roe_path: Path | None,
        paths: config.Paths,
        platform: str | None = None,
        program: str | None = None,
        max_turns: int | None = None,
        on_finished: Callable[[str], None] | None = None,
    ) -> None:
        profile = load_roe_profile(roe_path, RoeSourceType.MANUAL)
        if max_turns is not None:
            profile = _apply_max_turns(profile, max_turns)
        roe_policy = RoePolicy(profile)
        scope_policy = ScopePolicy(profile, base_url)
        budget = RequestBudget(profile)
        http_tool = HttpTool(base_url, roe_policy, scope_policy, budget)
        session = HackerSession()
        db_path = paths.program_db(platform or "local", program or "")
        session.seed_urls(_seed_urls(db_path, base_url))
        verifier = FindingVerifier(profile)
        provider = providers_mod.from_env()

        super().__init__(
            profile, roe_policy, http_tool, budget, session, verifier, provider,
        )

        self._run_id: str = uuid.uuid4().hex
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._next_task_hint: TaskType | None = None
        self._closed = False
        self._on_finished = on_finished

    # ── HackerLoop hook overrides ─────────────────────────────────────────

    def _pick_task(self) -> TaskType:
        if self._next_task_hint is not None:
            return self._next_task_hint
        if not self.session.observations:
            return TaskType.AGENT_PLANNING
        last = self.session.observations[-1]
        ctype = (last.headers.get("content-type") or "").lower()
        body = last.body or ""
        if "javascript" in ctype:
            return TaskType.CODING_SECURITY
        if "text/html" in ctype and "<script" in body.lower():
            return TaskType.CODING_SECURITY
        return TaskType.AGENT_PLANNING
```

Reuse `_seed_urls` from the existing CLI rather than redefining it (it's already in `src/earn_money/agent/hacker_loop_cli.py`). Add this import alongside the others at the top of `probe_runner.py`:

```python
from earn_money.agent.hacker_loop_cli import _seed_urls
```

`_apply_max_turns` is the runner-side single-knob clamp. The CLI's `_apply_cli_limits` does the same thing for four knobs but takes an `argparse.Namespace`; a proper extraction would refactor `_apply_cli_limits` to take a plain dict and live in a shared module. **Deferred** — out of plan scope; left as a TODO note here. For v1, `probe_runner` carries this small helper:

```python
def _apply_max_turns(profile: RoeProfile, max_turns: int) -> RoeProfile:
    # TODO: share with hacker_loop_cli._apply_cli_limits once that helper
    # is refactored to take a dict of overrides (out of scope for this PR).
    effective = min(profile.max_turns, max_turns)
    data = profile.model_dump(exclude={"source_type", "source_ref"})
    data["max_turns"] = effective
    return RoeProfile.from_dict(data, profile.source_type, profile.source_ref)


def _resolve_model_safely(task: TaskType) -> str | None:
    try:
        return resolve_model(task)
    except RouterUnconfigured:
        return None


def _est_tokens(text: str | None) -> int:
    return (len(text) // 4) if text else 0
```

- [ ] **Step 4: Run — expect the first `_pick_task` test to PASS**

```bash
uv run pytest tests/dashboard/test_probe_runner.py::TestPickTask -v
```

- [ ] **Step 5: Add remaining `_pick_task` tests**

```python
    def test_javascript_content_type_picks_coding_security(self):
        from earn_money.agent.observations import ObservationWrapper
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "application/javascript"}, "var x=1;",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.CODING_SECURITY

    def test_html_with_script_picks_coding_security(self):
        from earn_money.agent.observations import ObservationWrapper
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "text/html"}, "<html><script>1</script></html>",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.CODING_SECURITY

    def test_html_without_script_picks_agent_planning(self):
        from earn_money.agent.observations import ObservationWrapper
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "text/html"}, "<html><body>hi</body></html>",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.AGENT_PLANNING

    def test_json_content_type_picks_agent_planning(self):
        from earn_money.agent.observations import ObservationWrapper
        obs = ObservationWrapper.from_response(
            200, "https://t/x", {"content-type": "application/json"}, "{}",
        )
        r = _runner_with_session([obs])
        assert r._pick_task() == TaskType.AGENT_PLANNING

    def test_report_candidate_hint_picks_structured_extraction(self):
        r = _runner_with_session([])
        r._next_task_hint = TaskType.STRUCTURED_EXTRACTION
        assert r._pick_task() == TaskType.STRUCTURED_EXTRACTION
```

- [ ] **Step 6: Add hook overrides + `_get_llm_response` override**

In `probe_runner.py`, inside `ProbeRunner`, add:

```python
    def _get_llm_response(self, prompt: str) -> str | None:
        task = self._pick_task()
        self._last_model_id = _resolve_model_safely(task)
        try:
            return self.provider.complete(  # type: ignore[no-any-return]
                system=_SYSTEM_PROMPT, user=prompt, task=task,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            log.error("Provider error: %s", e)
            return None

    def _on_llm_response(self, turn: int, raw: str | None, model_id: str | None) -> None:
        self._emit("turn", {
            "turn": turn, "stage": "action_pending",
            "model": self._last_model_id,
            "raw_excerpt": (raw or "")[:200],
            "estimated_tokens": _est_tokens(raw),
        })

    def _on_action_parsed(self, turn: int, action: Any, parse_recovered: bool) -> None:
        self._emit("turn", {
            "turn": turn, "stage": "action_parsed",
            "action": action.model_dump(),
            "parse_recovered": parse_recovered,
        })

    def _on_policy_decision(self, turn: int, action: Any, decision: Any) -> None:
        self._emit("turn", {
            "turn": turn, "stage": "policy",
            "action": action.model_dump(),
            "policy": {"allowed": decision.allowed, "reason": decision.reason},
        })

    def _on_observation(self, turn: int, action: Any, obs: ObservationWrapper) -> None:
        self._emit("turn", {
            "turn": turn, "stage": "observation",
            "obs": {
                "status": obs.status,
                "url": obs.final_url,
                "body_excerpt": obs.body[:200],
                "content_type": obs.headers.get("content-type", ""),
            },
        })

    def _on_finding(self, turn: int, kind: str, finding: dict[str, Any]) -> None:
        self._emit("finding", {**finding, "turn": turn, "kind": kind})

    def _on_turn_complete(self, turn: int, action: Any, stage: str) -> None:
        if isinstance(action, ReportCandidateAction):
            self._next_task_hint = TaskType.STRUCTURED_EXTRACTION
        elif self._next_task_hint is not None:
            self._next_task_hint = None
        self._emit("turn", {"turn": turn, "stage": "complete", "outcome": stage})
        if self._stop_event.is_set():
            raise _StopRequested()
```

- [ ] **Step 7: Add lifecycle + `events()` + `_emit`**

Append to `ProbeRunner`:

```python
    def start(self) -> str:
        if self._thread is not None:
            raise AlreadyRunning(self._run_id)
        self._thread = threading.Thread(target=self._run_safe, daemon=True)
        self._thread.start()
        return self._run_id

    def stop(self) -> None:
        self._stop_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def run_id(self) -> str:
        return self._run_id

    # SSE convention is a keep-alive every 15-30 s; 15 here so a slow
    # LLM turn (≈10 s) doesn't trigger a keep-alive between real events,
    # but a paused server doesn't hold an idle TCP connection silent
    # past 30 s either.
    _EVENTS_GET_TIMEOUT_SECONDS = 15.0

    def events(self) -> Iterator[dict[str, Any]]:
        while True:
            try:
                evt = self._queue.get(timeout=self._EVENTS_GET_TIMEOUT_SECONDS)
            except queue.Empty:
                if not self.is_running() and self._queue.empty():
                    return
                yield {"event": "_keepalive", "data": {}}
                continue
            yield evt
            if evt.get("event") in ("done", "probe_error"):
                return

    # ── private helpers ──────────────────────────────────────────────────

    def _emit(self, name: str, data: dict[str, Any]) -> None:
        self._queue.put({"event": name, "data": data})

    def _run_safe(self) -> None:
        try:
            result = self.run()
            self._emit("done", _summarise(result))
        except _StopRequested:
            self._emit("done", {
                "turns": self._current_turn,
                "stop_reason": "operator_cancel",
                "candidates_count": len(self.session.candidate_findings),
                "verified_count":   len(self.session.verified_findings),
                "denials_count":    len(self.session.policy_denials),
            })
        except Exception as e:
            log.exception("ProbeRunner crashed")
            self._emit("probe_error", {"message": str(e), "stage": "runtime"})
        finally:
            self._closed = True
            if self._on_finished is not None:
                try:
                    self._on_finished(self._run_id)
                except Exception:
                    log.exception("on_finished callback raised")
```

Add the summary helper at module level:

```python
def _summarise(result: Any) -> dict[str, Any]:
    return {
        "turns": result.turns,
        "stop_reason": result.stop_reason,
        "candidates_count": len(result.candidate_findings),
        "verified_count":   len(result.verified_findings),
        "denials_count":    len(result.policy_denials),
    }
```

- [ ] **Step 8: Verify file size is under 200 lines**

```bash
wc -l src/earn_money/dashboard/probe_runner.py
```

Expected: ≤200. If over, split helpers into `probe_runner_events.py` (`_emit`, `_summarise`) and re-run.

- [ ] **Step 9: Add a shared fixture for ProbeRunner construction**

Append to `tests/dashboard/test_probe_runner.py`:

```python
import json
import re
from unittest.mock import patch

import pytest


@pytest.fixture()
def make_runner(tmp_path, monkeypatch):
    """Build a real ProbeRunner instance without starting its thread.

    Returns a factory that accepts canned LLM-reply strings (in order)
    and optional profile overrides. The factory bypasses the real
    OpenRouter provider and resolves RoE paths under tmp_path/roe."""

    def _factory(replies: list[str | None], **profile_overrides):
        from earn_money import config
        from earn_money.dashboard import probe_runner as pr

        (tmp_path / "RECON_ENABLED").touch()
        roe_dir = tmp_path / "roe"
        roe_dir.mkdir(exist_ok=True)
        roe_yaml = roe_dir / "test.yaml"
        roe_yaml.write_text(
            "name: test\n"
            "allowed_hosts: [target.example.com]\n"
            "max_requests: 100\nmax_posts: 20\nmax_turns: 10\n"
            "max_runtime_seconds: 60\nmax_response_bytes: 5000\n"
            "delay_between_requests_ms: 0\n"
            "allow_get: true\nallow_post: true\nallow_idor_checks: true\n"
        )

        provider = MagicMock()
        iter_replies = iter(replies)
        provider.complete.side_effect = lambda **_kw: next(iter_replies)
        monkeypatch.setattr(
            "earn_money.dashboard.probe_runner.providers_mod.from_env",
            lambda: provider,
        )

        paths = config.Paths.from_root(tmp_path)
        return pr.ProbeRunner(
            base_url="https://target.example.com",
            roe_path=roe_yaml,
            paths=paths,
        )

    return _factory


def _events_from(runner) -> list[dict]:
    """Drain runner._queue synchronously and return events as a list."""
    out: list[dict] = []
    while not runner._queue.empty():
        out.append(runner._queue.get_nowait())
    return out


def _j(**kwargs) -> str:
    return json.dumps(kwargs)
```

- [ ] **Step 10: Add `TestLifecycle` with concrete bodies**

```python
class TestLifecycle:
    def test_run_id_is_uuid4_hex(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        assert re.fullmatch(r"[0-9a-f]{32}", runner.run_id())

    def test_is_running_false_before_start(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        assert runner.is_running() is False

    def test_double_start_raises_already_running(self, make_runner):
        from earn_money.dashboard.probe_runner import AlreadyRunning
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner.start()
        with pytest.raises(AlreadyRunning):
            runner.start()
        # let the loop thread settle so it doesn't bleed into the next test
        if runner._thread is not None:
            runner._thread.join(timeout=2.0)

    def test_calls_on_finished_callback_after_natural_exit(self, make_runner):
        seen: list[str] = []
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner._on_finished = lambda run_id: seen.append(run_id)
        runner._run_safe()
        assert seen == [runner.run_id()]
```

- [ ] **Step 11: Add `TestEventEmission` with concrete bodies**

```python
class TestEventEmission:
    def test_emits_action_pending_before_parse(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner.run()
        names = [(e["data"].get("stage"), e["event"]) for e in _events_from(runner)]
        # First emitted turn-stage must be action_pending.
        first_action = next(
            (s for s, ev in names if ev == "turn" and s == "action_pending"), None,
        )
        assert first_action == "action_pending"

    def test_emits_action_parsed_after_parse(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner.run()
        stages = [e["data"].get("stage") for e in _events_from(runner) if e["event"] == "turn"]
        # action_pending must come before action_parsed in the same turn.
        assert "action_parsed" in stages
        assert stages.index("action_pending") < stages.index("action_parsed")

    def test_action_parsed_carries_parse_recovered_true_when_fenced(self, make_runner):
        fenced = "```json\n" + _j(tool="stop", category="stop", args={}) + "\n```"
        runner = make_runner([fenced])
        runner.run()
        parsed = [e["data"] for e in _events_from(runner)
                  if e["event"] == "turn" and e["data"].get("stage") == "action_parsed"]
        assert parsed and parsed[0]["parse_recovered"] is True

    def test_action_parsed_carries_parse_recovered_false_on_clean_json(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner.run()
        parsed = [e["data"] for e in _events_from(runner)
                  if e["event"] == "turn" and e["data"].get("stage") == "action_parsed"]
        assert parsed and parsed[0]["parse_recovered"] is False

    def test_emits_done_with_summary_on_natural_exit(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={"reason": "done"})])
        runner._run_safe()
        done = [e["data"] for e in _events_from(runner) if e["event"] == "done"]
        assert done and done[0]["stop_reason"] == "done"
        assert "turns" in done[0]
        assert "candidates_count" in done[0]

    def test_emits_done_with_operator_cancel_when_stopped(self, make_runner):
        from earn_money.dashboard.probe_runner import _StopRequested
        runner = make_runner(replies=[_j(tool="stop", category="stop", args={})])
        # Force _StopRequested to bubble out of run() by mocking the
        # base loop. _run_safe must convert it into a done event with
        # stop_reason=operator_cancel and the full summary payload.
        with patch.object(runner, "run", side_effect=_StopRequested()):
            runner._run_safe()
        done = [e["data"] for e in _events_from(runner) if e["event"] == "done"]
        assert done
        assert done[0]["stop_reason"] == "operator_cancel"
        for k in ("turns", "candidates_count", "verified_count", "denials_count"):
            assert k in done[0]

    def test_emits_probe_error_when_loop_crashes(self, make_runner):
        runner = make_runner(replies=[_j(tool="stop", category="stop", args={})])
        with patch.object(runner, "run", side_effect=RuntimeError("boom")):
            runner._run_safe()
        errs = [e["data"] for e in _events_from(runner) if e["event"] == "probe_error"]
        assert errs and "boom" in errs[0]["message"]
        assert errs[0]["stage"] == "runtime"

    def test_finding_event_protects_trusted_fields(self, make_runner):
        runner = make_runner(replies=[_j(tool="stop", category="stop", args={})])
        # Hostile verifier payload tries to overwrite turn / kind.
        runner._on_finding(turn=7, kind="candidate",
                           finding={"type": "idor", "turn": "BAD", "kind": "BAD"})
        evt = _events_from(runner)[-1]
        assert evt["event"] == "finding"
        assert evt["data"]["turn"] == 7
        assert evt["data"]["kind"] == "candidate"
```

- [ ] **Step 12: Add `TestStop` and `TestEvents` (queue draining)**

```python
class TestStop:
    def test_stop_sets_event_flag(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner.stop()
        assert runner._stop_event.is_set()

    def test_stop_causes_next_turn_complete_to_raise(self, make_runner):
        from earn_money.dashboard.probe_runner import _StopRequested
        from earn_money.agent.probe_actions import StopAction
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner._stop_event.set()
        with pytest.raises(_StopRequested):
            runner._on_turn_complete(1, StopAction(tool="stop", category="stop"), "completed")


class TestEvents:
    def test_events_returns_after_done_event(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        runner._emit("done", {"turns": 1, "stop_reason": "done",
                              "candidates_count": 0, "verified_count": 0,
                              "denials_count": 0})
        produced = []
        for evt in runner.events():
            produced.append(evt)
            if len(produced) >= 5:
                break  # guard against infinite loop
        assert produced[-1]["event"] == "done"

    def test_events_yields_keepalive_on_queue_idle(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        # Mark the runner as "still running" so the queue-empty branch
        # yields _keepalive instead of returning.
        runner._thread = MagicMock()
        runner._thread.is_alive = lambda: True
        gen = runner.events()
        evt = next(gen)
        assert evt == {"event": "_keepalive", "data": {}}
```

- [ ] **Step 13: Add `_pick_task` consume-after-use test**

```python
    def test_hint_is_consumed_after_one_use(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={})])
        # Simulate a ReportCandidateAction having just been processed.
        runner._next_task_hint = TaskType.STRUCTURED_EXTRACTION
        assert runner._pick_task() == TaskType.STRUCTURED_EXTRACTION
        # Trigger the _on_turn_complete branch that clears the hint.
        from earn_money.agent.probe_actions import StopAction
        runner._on_turn_complete(2, StopAction(tool="stop", category="stop"), "completed")
        assert runner._next_task_hint is None
```

- [ ] **Step 14: Run the full test suite — covers the new probe_runner tests and confirms no regression**

```bash
uv run pytest -q
```

(One sweep is enough — the file-level run that an earlier draft had here was redundant with the full sweep.)

- [ ] **Step 15: Lint**

```bash
uv run ruff check src/earn_money/dashboard/probe_runner.py tests/dashboard/test_probe_runner.py
```

- [ ] **Step 16: Commit**

```bash
git add src/earn_money/dashboard/probe_runner.py tests/dashboard/test_probe_runner.py
git commit -m "feat(dashboard): ProbeRunner — threaded HackerLoop with SSE event emission"
```
