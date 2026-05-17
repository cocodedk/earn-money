"""ProbeRunner — the dashboard's threaded HackerLoop subclass.

Overrides the six observation hooks added to `HackerLoop` and pushes
structured events onto a `queue.Queue`. Selects a per-turn task profile
from observation/action context, manages the loop thread, and clears
the server's slot via an `on_finished` callback so there's no circular
import.
"""
from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from earn_money import config
from earn_money.agent import providers as providers_mod
from earn_money.agent.budget import RequestBudget
from earn_money.agent.finding_verifier import FindingVerifier
from earn_money.agent.hacker_loop import (
    _SYSTEM_PROMPT,
    HackerLoop,
    _call_provider_with_rf_fallback,
)
from earn_money.agent.hacker_loop_cli import _seed_urls
from earn_money.agent.hacker_session import HackerSession
from earn_money.agent.http_tool import HttpTool
from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.probe_actions import ReportCandidateAction
from earn_money.agent.roe_policy import RoePolicy
from earn_money.agent.roe_profile import RoeProfile, RoeSourceType, load_roe_profile
from earn_money.agent.scope_policy import ScopePolicy
from earn_money.agent.task_router import RouterUnconfigured, TaskType, resolve_model
from earn_money.dashboard.probe_history import EventHistory

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
        target_kind: str,
        platform: str | None = None,
        program: str | None = None,
        max_turns: int | None = None,
        on_finished: Callable[[str], None] | None = None,
    ) -> None:
        profile = load_roe_profile(roe_path, RoeSourceType.MANUAL)
        # For target_kind=local_lab without an RoE file, the operator's
        # submission of the base_url through the form IS the scope
        # authorization — add its host to allowed_hosts so the LLM
        # doesn't immediately stop on "Allowed hosts: (empty)".
        if target_kind == "local_lab" and roe_path is None:
            profile = _augment_with_base_host(profile, base_url)
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
        self._history = EventHistory()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._next_task_hint: TaskType | None = None
        self._closed = False
        self._on_finished = on_finished

        # Emit run metadata as the very first history entry (seq=1).
        # A page-reload / second-tab subscriber gets this on replay and
        # can pre-fill the form fields so the operator sees what's
        # actually running.
        self._emit("meta", {
            "run_id": self._run_id,
            "base_url": base_url,
            "target_kind": target_kind,
            "platform": platform,
            "program": program,
            "roe_profile": str(roe_path) if roe_path is not None else "",
            "max_turns": profile.max_turns,
        })

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

    # ── private helpers ──────────────────────────────────────────────────

    def _emit(self, name: str, data: dict[str, Any]) -> None:
        self._history.append(name, data)

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
            # NOTE: we deliberately do NOT call _on_finished / clear the
            # server's _PROBE_SLOT here. If we did, a fast run (e.g. an
            # invalid-action exit on turn 1) could complete and clear the
            # slot BEFORE the browser's EventSource connects — the
            # stream route would then 404 and the operator never sees
            # the done / probe_error event. Leaving the slot in place
            # means:
            #   - The slot acts as "the most recent runner" (running or done).
            #   - The stream route still validates run_id, so a stale
            #     slot can't serve events to a different probe's client.
            #   - The next POST /api/probe/start overwrites the slot via
            #     the existing fast-409 path: `is_running()` returns
            #     False for a finished runner, so the new probe installs.
            #   - At most one stale-but-finished runner sits in memory
            #     at a time. Bounded; fine for a single-operator dashboard.
            #
            # `_on_finished` is kept on the constructor for future use
            # (e.g. multi-probe history), but is NOT invoked here.


def _augment_with_base_host(profile: RoeProfile, base_url: str) -> RoeProfile:
    host = urlparse(base_url).hostname
    if not host or host in profile.allowed_hosts:
        return profile
    data = profile.model_dump(exclude={"source_type", "source_ref"})
    data["allowed_hosts"] = [*profile.allowed_hosts, host]
    return RoeProfile.from_dict(data, profile.source_type, profile.source_ref)


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


def _summarise(result: Any) -> dict[str, Any]:
    return {
        "turns": result.turns,
        "stop_reason": result.stop_reason,
        "candidates_count": len(result.candidate_findings),
        "verified_count":   len(result.verified_findings),
        "denials_count":    len(result.policy_denials),
    }
