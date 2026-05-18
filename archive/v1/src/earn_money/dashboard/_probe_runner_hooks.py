"""ProbeRunner HackerLoop-hook overrides + lifecycle methods as a mixin.

Extracted from probe_runner.py to keep that module under the 200-line
file cap. The mixin assumes the concrete ProbeRunner provides:
  - self.provider, self.session, self._stop_event, self._thread
  - self._emit(name, data), self._run_safe(), self._history
  - self._next_task_hint, self._last_model_id, self._current_turn, self._run_id

It has no state of its own — it only houses the six observation hooks
the dashboard turns into SSE events, plus the lifecycle methods.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator
from typing import Any

from earn_money.agent.hacker_loop import _SYSTEM_PROMPT, _call_provider_with_rf_fallback
from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.probe_actions import ReportCandidateAction
from earn_money.agent.task_router import TaskType
from earn_money.dashboard.probe_history import EventHistory

from ._probe_runner_helpers import _est_tokens, _resolve_model_safely


class _StopRequested(Exception):
    """Internal: raised to break out of the loop on operator-cancel."""


class AlreadyRunning(Exception):
    """Raised by ProbeRunner.start() when a second start is attempted on
    the same instance. Defined here (not in probe_runner.py) so the mixin
    can raise it without needing a back-reference; probe_runner.py
    re-exports the name for compatibility with existing importers."""


class ProbeRunnerHooksMixin:
    # Attributes declared here for the type checker; assigned by the
    # concrete ProbeRunner subclass's __init__ before any mixin method
    # is called. The mixin holds no state of its own.
    _thread: threading.Thread | None
    _stop_event: threading.Event
    _run_id: str
    _history: EventHistory
    _next_task_hint: TaskType | None
    _last_model_id: str | None
    session: Any
    provider: Any

    def _run_safe(self) -> None:  # implemented by ProbeRunner subclass
        raise NotImplementedError

    # ── lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> str:
        if self._thread is not None:
            raise AlreadyRunning(self._run_id)
        self._thread = threading.Thread(target=self._run_safe, daemon=True)
        self._thread.start()
        return self._run_id

    def stop(self) -> None:
        """Cooperative cancel. Sets a threading.Event flag; the override
        of `_on_turn_complete` checks the flag and raises `_StopRequested`
        at the END of the current iteration. That means stop() does NOT
        interrupt an in-flight `provider.complete(...)` call or an
        in-flight `http_tool.get/post(...)` call — those finish first.
        Worst-case wait between calling stop() and the runner exiting:
        one LLM round-trip plus (for get/post turns) one HTTP round-trip,
        bounded by their respective timeouts. Acceptable for v1; a
        stronger cancel would need explicit provider/http timeouts, not
        thread killing (which Python doesn't safely support)."""
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

    def events(self, last_event_id: int = 0) -> Iterator[dict[str, Any]]:
        """Yield SSE events from the per-run history. `last_event_id`
        comes from the browser's SSE `Last-Event-ID` header on reconnect;
        a fresh subscriber passes 0 (the default) to receive the full
        replay."""
        yield from self._history.iter_since(
            last_event_id, keepalive_interval=self._EVENTS_GET_TIMEOUT_SECONDS,
        )

    def _emit(self, name: str, data: dict[str, Any]) -> None:
        self._history.append(name, data)

    # ── task selection ────────────────────────────────────────────────────

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

    # ── HackerLoop hook overrides ─────────────────────────────────────────

    def _get_llm_response(
        self, prompt: str, *, with_response_format: bool = True,
    ) -> tuple[str | None, bool]:
        task = self._pick_task()
        self._last_model_id = _resolve_model_safely(task)
        return _call_provider_with_rf_fallback(
            self.provider, system=_SYSTEM_PROMPT, user=prompt, task=task,
            with_response_format=with_response_format,
        )

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
