# 05 — ProbeRunner

New file: `src/earn_money/dashboard/probe_runner.py`. Subclasses `HackerLoop`, overrides the hooks added in [02-hacker-loop-hooks.md](02-hacker-loop-hooks.md), and picks the task per turn per the rules in [03-task-routing.md](03-task-routing.md).

Target: ≤200 lines. If the wiring grows past that, split helpers into `probe_runner_events.py` (event-shaping pure functions) and `probe_runner_select.py` (the `_pick_task` ladder).

## Public surface

```python
class ProbeRunner:
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
    ) -> None: ...

    def start(self) -> str:
        """Spawn the loop thread, return a run_id (uuid4 hex). Raises
        AlreadyRunning if start() was already called on this instance."""

    def events(self) -> Iterator[dict[str, Any]]:
        """Yield queue events until done/probe_error. Blocks on the queue with
        a per-iteration timeout so the SSE handler can flush keep-alive
        comments if the loop is mid-LLM-call."""

    def stop(self) -> None:
        """Operator-cancel. Sets the stop event; the next inter-turn
        checkpoint exits with stop_reason='operator_cancel'."""

    def is_running(self) -> bool: ...
    def run_id(self) -> str: ...
```

Keyword-only constructor (resolves cursor-agent review #3): the dashboard form provides `base_url` and an optional RoE path; `platform`/`program` are optional and only used for the FROZEN gate. `paths` is required for `RECON_ENABLED` resolution and is supplied by the server, not the form.

The `on_finished` callback (resolves second-reviewer #3) is invoked with `self._run_id` inside the runner's `finally` block when the loop thread exits — success, error, or operator-cancel alike. The server passes a closure that clears `_PROBE_SLOT`. The runner never imports from `server.py`, so there's no circular import.

## Internals

```python
class ProbeRunner(HackerLoop):
    def __init__(self, *, base_url, roe_path, paths, platform=None, program=None,
                 max_turns=None, on_finished=None):
        profile = load_roe_profile(roe_path, RoeSourceType.MANUAL)
        if max_turns is not None:
            profile = _apply_max_turns(profile, max_turns)  # reuse helper
        roe_policy = RoePolicy(profile)
        scope_policy = ScopePolicy(profile, base_url)
        budget = RequestBudget(profile)
        http_tool = HttpTool(base_url, roe_policy, scope_policy, budget)
        session = HackerSession()
        # seed urls from the program's SQLite (if any) — same logic as CLI
        db_path = paths.program_db(platform or "local", program or "")
        session.seed_urls(_seed_urls(db_path, base_url))
        verifier = FindingVerifier(profile)
        provider = providers_mod.from_env()

        super().__init__(profile, roe_policy, http_tool, budget, session,
                         verifier, provider)

        self._run_id = uuid.uuid4().hex
        self._queue: queue.Queue[dict] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_model_id: str | None = None
        self._next_task_hint: str | None = None
        self._closed = False    # mirrors the "closed" flag the client uses
        self._on_finished = on_finished

    # ── HackerLoop hook overrides ─────────────────────────────────────────────

    def _get_llm_response(self, prompt: str) -> str | None:
        task = self._pick_task()
        self._last_model_id = _resolve_model_safely(task)
        try:
            return self.provider.complete(
                system=_SYSTEM_PROMPT, user=prompt, task=task,
                response_format={"type": "json_object"},   # ← per 04-robust-action-parsing.md
            )
        except Exception as e:
            log.error("Provider error: %s", e)
            return None

    def _on_llm_response(self, turn, raw, model_id):
        self._emit("turn", {
            "turn": turn, "stage": "action_pending",
            "model": self._last_model_id,
            "raw_excerpt": (raw or "")[:200],
            "estimated_tokens": _est_tokens(raw),
        })

    def _on_action_parsed(self, turn, action, parse_recovered):
        self._emit("turn", {
            "turn": turn, "stage": "action_parsed",
            "action": action.model_dump(),
            "parse_recovered": parse_recovered,
        })

    def _on_policy_decision(self, turn, action, decision):
        self._emit("turn", {
            "turn": turn, "stage": "policy",
            "action": action.model_dump(),
            "policy": {"allowed": decision.allowed, "reason": decision.reason},
        })

    def _on_observation(self, turn, action, obs):
        self._emit("turn", {
            "turn": turn, "stage": "observation",
            "obs": {
                "status": obs.status,
                "url": obs.final_url,
                "body_excerpt": obs.body[:200],
                "content_type": obs.headers.get("content-type", ""),
            },
        })

    def _on_finding(self, turn, kind, finding):
        # Spread the untrusted finding FIRST, then overwrite with our
        # trusted turn/kind values — protects against a verifier output
        # that happens to carry a 'turn' or 'kind' key.
        self._emit("finding", {**finding, "turn": turn, "kind": kind})

    def _on_turn_complete(self, turn, action, stage):
        if isinstance(action, ReportCandidateAction):
            self._next_task_hint = "structured_extraction"
        elif self._next_task_hint == "structured_extraction":
            self._next_task_hint = None
        self._emit("turn", {"turn": turn, "stage": "complete", "outcome": stage})
        if self._stop_event.is_set():
            raise _StopRequested()
```

## `_pick_task` (decisive — resolves review #2)

```python
def _pick_task(self) -> str:
    if self._next_task_hint:
        return self._next_task_hint
    if not self.session.observations:
        return "agent_planning"   # NOT deep_reasoning; see 03-task-routing.md
    last = self.session.observations[-1]
    ctype = (last.headers.get("content-type") or "").lower()
    body = last.body or ""
    if "javascript" in ctype:
        return "coding_security"
    if "text/html" in ctype and "<script" in body.lower():
        return "coding_security"
    return "agent_planning"
```

Pure function of session state — fully unit-testable by feeding canned `ObservationWrapper`s and asserting the return value.

## Thread lifecycle

```python
def start(self) -> str:
    if self._thread is not None:
        raise AlreadyRunning(self._run_id)
    self._thread = threading.Thread(target=self._run_safe, daemon=True)
    self._thread.start()
    return self._run_id

def _run_safe(self) -> None:
    try:
        result = self.run()                # inherited from HackerLoop
        self._emit("done", _summarise(result))
    except _StopRequested:
        # Emit the same shape as the natural-exit done event so the
        # frontend renderer can read `turns` / `*_count` fields without
        # special-casing operator_cancel.
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
        # The SSE drain reads "done"/"probe_error" → exits cleanly.
        if self._on_finished is not None:
            try:
                self._on_finished(self._run_id)
            except Exception:
                log.exception("on_finished callback raised")

def stop(self) -> None:
    self._stop_event.set()

def is_running(self) -> bool:
    return self._thread is not None and self._thread.is_alive()
```

## `events()` — SSE drain side

```python
def events(self) -> Iterator[dict]:
    while True:
        try:
            evt = self._queue.get(timeout=1.0)
        except queue.Empty:
            if not self.is_running() and self._queue.empty():
                return
            # keep-alive: the SSE route may emit ":\n\n" comments to keep
            # the connection warm during long LLM round-trips.
            yield {"event": "_keepalive", "data": {}}
            continue
        yield evt
        if evt.get("event") in ("done", "probe_error"):
            return
```

Each `evt` is `{"event": "<name>", "data": {...}}`. The SSE route formats it as `event: <name>\ndata: <json>\n\n`. The terminal events are `done` and `probe_error` — note the rename from `error` so we don't collide with `EventSource`'s built-in transport `error` event.

## `_emit` helper

```python
def _emit(self, name: str, data: dict[str, Any]) -> None:
    self._queue.put({"event": name, "data": data})
```

Single chokepoint — easy to mock, easy to test.

## Helpers in this file

- `_est_tokens(text)` — rough `len(text) // 4` for the per-turn badge. Returns 0 for `None`. Used to address review #7 (budget visibility).
- `_resolve_model_safely(task)` — `task_router.resolve_model(task)` wrapped in a `try/except RouterUnconfigured: return None`.
- `_summarise(result)` — flatten `LoopResult` into a `done` event payload (`turns`, `stop_reason`, `candidates_count`, `verified_count`, `denials_count`).
- `_seed_urls(db_path, base_url)` — same SQL as in `hacker_loop_cli.py:_seed_urls` (lifted unchanged into this file, or extracted to a shared module if it grows a second caller).
- `_apply_max_turns(profile, max_turns)` — single-knob version of the CLI's `_apply_cli_limits`; consider extracting both into `agent/roe_profile.py` later if the duplication bothers you. **Not** in scope for this spec.

## Test surface

- `tests/dashboard/test_probe_runner.py` constructs a `ProbeRunner` with a mock `Provider` whose `complete` returns canned action JSON, then asserts the queue events fire in the documented order ([01-architecture.md](01-architecture.md) §"Data flow per turn") and that `_pick_task` returns the right `TaskType` for each canned `ObservationWrapper`.

Detail in [12-tests.md](12-tests.md).
