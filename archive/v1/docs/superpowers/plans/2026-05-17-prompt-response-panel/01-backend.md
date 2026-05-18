# Backend tasks (B1–B8)

Each task: write the failing test first (`pytest -x -k <name>` should fail), then minimal impl, then green, then commit, then `/simplify` on the changed files.

Project test invocation: `uv run pytest -x` for fail-fast; `uv run pytest --cov=src/earn_money --cov-report=term-missing` for coverage.

---

## B1: Helper-direct tests for `_call_provider_with_rf_fallback`

**Files:**
- Modify: `tests/agent/test_hacker_loop.py` — add `TestProviderHelper` class

**Pure addition.** Verifies the existing helper contract (already in `hacker_loop.py:260-285`) before downstream code starts depending on it.

- [ ] **Step 1: Write the failing tests.**

```python
# tests/agent/test_hacker_loop.py (append after TestResponseFormatPassthrough)

class TestProviderHelper:
    def test_returns_used_response_format_true_when_rf_succeeds(self):
        from earn_money.agent.hacker_loop import _call_provider_with_rf_fallback
        from earn_money.agent.task_router import TaskType
        provider = MagicMock()
        provider.complete.return_value = '{"tool":"stop","category":"stop","args":{}}'
        raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert raw.startswith("{")
        assert used_rf is True
        assert provider.complete.call_args.kwargs.get("response_format") == {"type": "json_object"}

    def test_returns_used_response_format_false_when_caller_passes_false(self):
        from earn_money.agent.hacker_loop import _call_provider_with_rf_fallback
        from earn_money.agent.task_router import TaskType
        provider = MagicMock()
        provider.complete.return_value = '{"tool":"stop","category":"stop","args":{}}'
        raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=False,
        )
        assert used_rf is False
        assert "response_format" not in provider.complete.call_args.kwargs

    def test_returns_used_response_format_false_when_rf_call_raises(self):
        from earn_money.agent.hacker_loop import _call_provider_with_rf_fallback
        from earn_money.agent.task_router import TaskType
        provider = MagicMock()
        provider.complete.side_effect = [
            RuntimeError("response_format unsupported"),
            '{"tool":"stop","category":"stop","args":{}}',
        ]
        raw, used_rf = _call_provider_with_rf_fallback(
            provider, system="s", user="u",
            task=TaskType.AGENT_PLANNING, with_response_format=True,
        )
        assert used_rf is False
        assert raw is not None
```

- [ ] **Step 2: Run.** `uv run pytest -x tests/agent/test_hacker_loop.py::TestProviderHelper -v` — all three should pass first try (helper already returns the tuple).
- [ ] **Step 3: Commit.** `test(probe-panel): add TestProviderHelper tests for tuple-return contract`
- [ ] **Step 4: `/simplify`.** No code changed, but run anyway.

---

## B2: Refactor `_get_llm_response` to return the tuple at the wrapper layer

**Files:**
- Modify: `src/earn_money/agent/hacker_loop.py` — change `_get_llm_response` signature + `run()` call sites
- Modify: `src/earn_money/dashboard/probe_runner.py` — mirror change in override
- Test: existing tests still pass; no new tests needed (B3's hook tests will lock the contract in)

- [ ] **Step 1: Modify `hacker_loop.py:239-248`.** Drop `self._last_used_response_format` assignment; return the tuple:

```python
def _get_llm_response(
    self, prompt: str, *, with_response_format: bool = True,
) -> tuple[str | None, bool]:
    return _call_provider_with_rf_fallback(
        self.provider, system=_SYSTEM_PROMPT, user=prompt,
        task=TaskType.AGENT_PLANNING,
        with_response_format=with_response_format,
    )
```

- [ ] **Step 2: Modify `run()` call sites (lines 121, 139–140).** Unpack the tuple into a local `used_rf`. Replace the `self._last_used_response_format` guard at line 132 with the local. Delete the `self._last_used_response_format` instance attribute entirely (no longer needed):

```python
raw, used_rf = self._get_llm_response(prompt)
self._on_llm_response(turn, raw, self._last_model_id)
# ... in except ActionParseError:
if not used_rf:
    return self._result(turn, "invalid_action")
raw, used_rf = self._get_llm_response(prompt, with_response_format=False)
self._on_llm_response(turn, raw, self._last_model_id)
```

Also delete line 83 (`self._last_used_response_format: bool = False`) from `__init__`.

- [ ] **Step 3: Mirror in `probe_runner.py:112-122`.** Override returns tuple; also delete the `self._last_used_response_format = used_rf` line:

```python
def _get_llm_response(
    self, prompt: str, *, with_response_format: bool = True,
) -> tuple[str | None, bool]:
    task = self._pick_task()
    self._last_model_id = _resolve_model_safely(task)
    return _call_provider_with_rf_fallback(
        self.provider, system=_SYSTEM_PROMPT, user=prompt, task=task,
        with_response_format=with_response_format,
    )
```

- [ ] **Step 4: Run.** `uv run pytest -x tests/agent/test_hacker_loop.py tests/dashboard/test_probe_runner.py` — all green.
- [ ] **Step 5: Commit.** `refactor(probe-panel): _get_llm_response returns (raw, used_response_format) tuple`
- [ ] **Step 6: `/simplify`.** Review changed files.

---

## B3: Extend `_on_llm_response` signature with system/prompt/attempt/used_response_format

**Files:**
- Modify: `src/earn_money/agent/hacker_loop.py` — hook signature + run() call sites
- Modify: `tests/agent/test_hacker_loop.py` — add `TestPromptHook` class

- [ ] **Step 1: Write failing tests.**

```python
class TestPromptHook:
    def test_called_with_prompt_and_system_on_first_call(self):
        loop = _loop([_j(tool="stop", category="stop", args={"reason": "done"})])
        seen: list[dict] = []
        loop._on_llm_response = lambda turn, raw, model_id, **kw: seen.append(kw)  # type: ignore[method-assign]
        loop.run()
        assert len(seen) == 1
        kw = seen[0]
        assert kw["attempt"] == 1
        assert kw["used_response_format"] is True
        assert "=== Rules of Engagement ===" in kw["prompt"]
        assert kw["system"].startswith("You are assisting with authorized security testing.")

    def test_called_twice_on_parse_retry(self):
        loop = _loop([])
        loop.provider.complete.side_effect = [
            "{",
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ]
        seen: list[dict] = []
        loop._on_llm_response = lambda turn, raw, model_id, **kw: seen.append(kw)  # type: ignore[method-assign]
        loop.run()
        assert [s["attempt"] for s in seen] == [1, 2]
        assert [s["used_response_format"] for s in seen] == [True, False]
        assert seen[0]["prompt"] == seen[1]["prompt"]
        assert seen[0]["system"] == seen[1]["system"]

    def test_attempt_2_only_when_retry_fires(self):
        loop = _loop([_j(tool="stop", category="stop", args={"reason": "done"})])
        seen: list[dict] = []
        loop._on_llm_response = lambda turn, raw, model_id, **kw: seen.append(kw)  # type: ignore[method-assign]
        loop.run()
        assert [s["attempt"] for s in seen] == [1]

    def test_attempt_1_used_response_format_false_when_provider_rejects_rf(self):
        loop = _loop([])
        loop.provider.complete.side_effect = [
            RuntimeError("response_format unsupported"),
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ]
        seen: list[dict] = []
        loop._on_llm_response = lambda turn, raw, model_id, **kw: seen.append(kw)  # type: ignore[method-assign]
        loop.run()
        assert len(seen) == 1
        assert seen[0]["attempt"] == 1
        assert seen[0]["used_response_format"] is False
```

- [ ] **Step 2: Run.** `uv run pytest -x tests/agent/test_hacker_loop.py::TestPromptHook` — fails: TypeError "unexpected keyword argument".
- [ ] **Step 3: Modify hook signature in `hacker_loop.py:87-89`:**

```python
def _on_llm_response(
    self, turn: int, raw: str | None, model_id: str | None,
    *, system: str, prompt: str, attempt: int, used_response_format: bool,
) -> None:
    """Called once per (turn, attempt). `raw` may be None when the provider raised."""
```

- [ ] **Step 4: Modify `run()` call sites to pass new kwargs (no instance-state round-trip).**

```python
prompt = self._build_prompt()
raw, used_rf = self._get_llm_response(prompt)
self._on_llm_response(
    turn, raw, self._last_model_id,
    system=_SYSTEM_PROMPT, prompt=prompt, attempt=1, used_response_format=used_rf,
)
# ...
# In except ActionParseError, after second call:
raw, used_rf = self._get_llm_response(prompt, with_response_format=False)
self._on_llm_response(
    turn, raw, self._last_model_id,
    system=_SYSTEM_PROMPT, prompt=prompt, attempt=2, used_response_format=used_rf,
)
```

- [ ] **Step 5: Run.** Tests pass. Also rerun existing `TestHooks` / `TestResponseFormatPassthrough` — they use `lambda *_a, **_k:` so they survive untouched.
- [ ] **Step 6: Commit.** `feat(probe-panel): _on_llm_response gains system/prompt/attempt/used_response_format`
- [ ] **Step 7: `/simplify`.**

---

## B4: Extend `_on_action_parsed` with `attempt` kwarg

**Files:**
- Modify: `src/earn_money/agent/hacker_loop.py`
- Modify: `tests/agent/test_hacker_loop.py` — extend `TestHooks::test_on_action_parsed_fires_after_parsing` (its positional lambda is the one case that breaks)
- Modify: `tests/agent/test_hacker_loop.py` — add `TestAttemptIdentity` class (start with happy path only)

- [ ] **Step 1: Fix the one breaking test.** `TestHooks.test_on_action_parsed_fires_after_parsing` (line 194-208) uses a positional `lambda turn, action, parse_recovered: …`. Update to absorb kwargs:

```python
loop._on_action_parsed = (  # type: ignore[method-assign]
    lambda turn, action, parse_recovered, **_k: seen.append(
        (turn, action.__class__, parse_recovered)
    )
)
```

- [ ] **Step 2: Add `TestAttemptIdentity` (happy-path only here; failure paths land in B5).**

```python
class TestAttemptIdentity:
    def test_action_parsed_carries_attempt_1_when_first_call_parses(self):
        loop = _loop([_j(tool="stop", category="stop", args={"reason": "done"})])
        seen: list[int] = []
        loop._on_action_parsed = lambda turn, action, parse_recovered, **kw: seen.append(kw["attempt"])  # type: ignore[method-assign]
        loop.run()
        assert seen == [1]

    def test_action_parsed_carries_attempt_2_when_retry_recovers(self):
        loop = _loop([])
        loop.provider.complete.side_effect = [
            "{",
            _j(tool="stop", category="stop", args={"reason": "done"}),
        ]
        seen: list[tuple[int, bool]] = []
        loop._on_action_parsed = lambda turn, action, parse_recovered, **kw: seen.append((kw["attempt"], parse_recovered))  # type: ignore[method-assign]
        loop.run()
        assert seen == [(2, True)]
```

- [ ] **Step 3: Run.** Fails: TypeError or missing kwarg.
- [ ] **Step 4: Modify hook signature in `hacker_loop.py:91`:**

```python
def _on_action_parsed(
    self, turn: int, action: object, parse_recovered: bool, *, attempt: int,
) -> None:
    """Called after `parse_action_with_recovery` returns."""
```

- [ ] **Step 5: Track which call's parse succeeded via a local `attempt` variable.** Keep `_on_action_parsed` called once per turn (current placement at line 148, AFTER the try/except). Set `attempt` in each branch:

```python
try:
    action, parse_recovered = parse_action_with_recovery(raw)
    attempt = 1
except ActionParseError as first_err:
    if not used_rf:
        return self._result(turn, "invalid_action")
    raw, used_rf = self._get_llm_response(prompt, with_response_format=False)
    self._on_llm_response(turn, raw, self._last_model_id,
                         system=_SYSTEM_PROMPT, prompt=prompt,
                         attempt=2, used_response_format=used_rf)
    if raw is None: return self._result(turn, "llm_error")
    try:
        action, parse_recovered = parse_action_with_recovery(raw)
        attempt = 2
    except ActionParseError as second_err:
        return self._result(turn, "invalid_action")
self._on_action_parsed(turn, action, parse_recovered, attempt=attempt)
```

Local `attempt` is structurally tied to which `parse_action_with_recovery` succeeded — no instance state, no future-clobber risk. (B5 adds the `_on_action_parse_failed` calls in the two `except` blocks.)

- [ ] **Step 6: Run.** Tests pass.
- [ ] **Step 7: Commit.** `feat(probe-panel): _on_action_parsed carries attempt`
- [ ] **Step 8: `/simplify`.**

---

## B5: New `_on_action_parse_failed` hook

**Files:**
- Modify: `src/earn_money/agent/hacker_loop.py`
- Modify: `tests/agent/test_hacker_loop.py` — finish `TestAttemptIdentity`

- [ ] **Step 1: Add failing tests to `TestAttemptIdentity`.**

```python
def test_on_action_parse_failed_called_with_attempt_1_when_first_attempt_fails(self):
    loop = _loop([])
    loop.provider.complete.side_effect = [
        "{",
        _j(tool="stop", category="stop", args={"reason": "done"}),
    ]
    seen: list[tuple[int, str]] = []
    loop._on_action_parse_failed = lambda turn, attempt, error: seen.append((attempt, error))  # type: ignore[method-assign,attr-defined]
    loop.run()
    assert len(seen) == 1
    assert seen[0][0] == 1
    assert seen[0][1]  # non-empty

def test_on_action_parse_failed_called_twice_when_both_attempts_fail(self):
    loop = _loop([])
    loop.provider.complete.side_effect = ["{", "still garbage"]
    seen: list[int] = []
    loop._on_action_parse_failed = lambda turn, attempt, error: seen.append(attempt)  # type: ignore[method-assign,attr-defined]
    loop.run()
    assert seen == [1, 2]

def test_no_action_parse_failed_on_happy_path(self):
    loop = _loop([_j(tool="stop", category="stop", args={"reason": "done"})])
    seen: list[int] = []
    loop._on_action_parse_failed = lambda turn, attempt, error: seen.append(attempt)  # type: ignore[method-assign,attr-defined]
    loop.run()
    assert seen == []
```

- [ ] **Step 2: Run.** Fails: AttributeError, no method `_on_action_parse_failed`.
- [ ] **Step 3: Add hook to `HackerLoop` (next to the other `_on_*` hooks):**

```python
def _on_action_parse_failed(self, turn: int, attempt: int, error: str) -> None:
    """Called from inside the `except ActionParseError` block in `run()`."""
```

- [ ] **Step 4: Wire from `run()`.** Inside the first `except ActionParseError as first_err`, BEFORE the retry-skip return:

```python
except ActionParseError as first_err:
    self._on_action_parse_failed(turn, 1, str(first_err))
    if not used_rf:
        return self._result(turn, "invalid_action")
    raw, used_rf = self._get_llm_response(prompt, with_response_format=False)
    self._on_llm_response(turn, raw, self._last_model_id,
                         system=_SYSTEM_PROMPT, prompt=prompt,
                         attempt=2, used_response_format=used_rf)
    if raw is None: return self._result(turn, "llm_error")
    try:
        action, parse_recovered = parse_action_with_recovery(raw)
    except ActionParseError as second_err:
        self._on_action_parse_failed(turn, 2, str(second_err))
        return self._result(turn, "invalid_action")
```

- [ ] **Step 5: Run.** Tests pass.
- [ ] **Step 6: Commit.** `feat(probe-panel): _on_action_parse_failed hook fires per failed parse`
- [ ] **Step 7: `/simplify`.**

---

## B6: ProbeRunner emits new fields on `action_pending`

**Files:**
- Modify: `src/earn_money/dashboard/probe_runner.py:124-130`
- Modify: `tests/dashboard/test_probe_runner.py` — add `TestPromptInSseEvent`

- [ ] **Step 1: Write failing tests.** Reuse existing `test_probe_runner.py` helpers: `make_runner` (pytest fixture at line 102) and `_events_from(runner)` (line 145):

```python
class TestPromptInSseEvent:
    def test_action_pending_event_includes_full_prompt_system_and_long_raw(self, make_runner):
        full_raw = '{"tool":"stop","category":"stop","args":{"reason":"' + "x" * 250 + '"}}'
        runner = make_runner([full_raw])
        runner.run()  # synchronous; emits events to runner._queue
        d = next(e["data"] for e in _events_from(runner)
                 if e["data"].get("stage") == "action_pending")
        assert d["prompt"]
        assert d["system"]
        assert d["raw"] == full_raw
        assert d["raw_excerpt"] == full_raw[:200]
        assert len(d["raw"]) > len(d["raw_excerpt"])
        assert d["attempt"] == 1
        assert d["used_response_format"] is True
```

For exception-raising cases (e.g., the `provider rejects rf` SSE test), follow the existing pattern at `test_probe_runner.py:282-286`: `make_runner(replies=[])` then `runner.provider.complete.side_effect = [RuntimeError(...), valid_json]`.

- [ ] **Step 2: Run.** Fails: KeyError or missing field.
- [ ] **Step 3: Override `_on_llm_response` in `probe_runner.py:124`:**

```python
def _on_llm_response(
    self, turn: int, raw: str | None, model_id: str | None,
    *, system: str, prompt: str, attempt: int, used_response_format: bool,
) -> None:
    self._emit("turn", {
        "turn": turn, "stage": "action_pending",
        "model": self._last_model_id,
        "attempt": attempt,
        "used_response_format": used_response_format,
        "system": system,
        "prompt": prompt,
        "raw": raw or "",
        "raw_excerpt": (raw or "")[:200],
        "estimated_tokens": _est_tokens(raw),
    })
```

- [ ] **Step 4: Run.** Pass.
- [ ] **Step 5: Commit.** `feat(probe-panel): action_pending SSE event carries prompt/system/raw/attempt`
- [ ] **Step 6: `/simplify`.**

---

## B7 + B8: ProbeRunner emits `attempt` on `action_parsed` and new `action_parse_failed` event

**Files:**
- Modify: `src/earn_money/dashboard/probe_runner.py:132-137` + add `_on_action_parse_failed` override
- Modify: `tests/dashboard/test_probe_runner.py` — add `TestAttemptIdentityInSseEvent`

- [ ] **Step 1: Write failing tests.**

```python
class TestAttemptIdentityInSseEvent:
    def test_action_parsed_event_carries_attempt(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={"reason": "done"})])
        runner.run()
        e = next(ev for ev in _events_from(runner)
                 if ev["data"].get("stage") == "action_parsed")
        assert e["data"]["attempt"] == 1

    def test_action_parse_failed_event_emitted_on_first_failure(self, make_runner):
        runner = make_runner(["{", _j(tool="stop", category="stop", args={"reason": "done"})])
        runner.run()
        f = next(ev for ev in _events_from(runner)
                 if ev["data"].get("stage") == "action_parse_failed")
        assert f["data"]["attempt"] == 1
        assert f["data"]["error"]

    def test_action_parse_failed_event_not_emitted_on_happy_path(self, make_runner):
        runner = make_runner([_j(tool="stop", category="stop", args={"reason": "done"})])
        runner.run()
        assert not any(ev["data"].get("stage") == "action_parse_failed"
                       for ev in _events_from(runner))
```

- [ ] **Step 2: Run.** Fails.
- [ ] **Step 3: Update `_on_action_parsed` override + add `_on_action_parse_failed` override:**

```python
def _on_action_parsed(
    self, turn: int, action: Any, parse_recovered: bool, *, attempt: int,
) -> None:
    self._emit("turn", {
        "turn": turn, "stage": "action_parsed",
        "attempt": attempt,
        "action": action.model_dump(),
        "parse_recovered": parse_recovered,
    })

def _on_action_parse_failed(self, turn: int, attempt: int, error: str) -> None:
    self._emit("turn", {
        "turn": turn, "stage": "action_parse_failed",
        "attempt": attempt, "error": error,
    })
```

- [ ] **Step 4: Run.** Pass.
- [ ] **Step 5: Commit.** `feat(probe-panel): action_parsed gains attempt; new action_parse_failed event`
- [ ] **Step 6: `/simplify`.**

---

**Backend complete.** All Python tests green. Continue with `02-frontend.md`.
