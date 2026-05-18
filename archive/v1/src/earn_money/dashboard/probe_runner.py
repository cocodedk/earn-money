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
from collections.abc import Callable
from pathlib import Path
from typing import Any

from earn_money import config
from earn_money.agent import providers as providers_mod
from earn_money.agent.budget import RequestBudget
from earn_money.agent.finding_verifier import FindingVerifier
from earn_money.agent.hacker_loop import HackerLoop
from earn_money.agent.hacker_loop_cli import _seed_urls
from earn_money.agent.hacker_session import HackerSession
from earn_money.agent.http_tool import HttpTool
from earn_money.agent.roe_policy import RoePolicy
from earn_money.agent.roe_profile import RoeSourceType, load_roe_profile
from earn_money.agent.scope_policy import ScopePolicy
from earn_money.agent.task_router import TaskType
from earn_money.dashboard.probe_history import EventHistory

from ._probe_runner_helpers import (
    _apply_max_turns,
    _augment_with_base_host,
    _summarise,
)
from ._probe_runner_hooks import AlreadyRunning, ProbeRunnerHooksMixin, _StopRequested

log = logging.getLogger(__name__)

# Re-exported so existing tests can `from earn_money.dashboard.probe_runner
# import AlreadyRunning, _augment_with_base_host, _StopRequested` without
# knowing the split.
__all__ = [
    "AlreadyRunning",
    "ProbeRunner",
    "_StopRequested",
    "_augment_with_base_host",
    "providers_mod",
]


class ProbeRunner(ProbeRunnerHooksMixin, HackerLoop):
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

        # Static run metadata — emitted once as the seq=1 history entry
        # (so SSE subscribers see it on replay) AND exposed via
        # `metadata()` so the `/api/probe/current` endpoint can answer
        # "what is currently running?" without parsing the history.
        self._static_meta: dict[str, Any] = {
            "run_id": self._run_id,
            "base_url": base_url,
            "target_kind": target_kind,
            "platform": platform,
            "program": program,
            "roe_profile": str(roe_path) if roe_path is not None else "",
            "max_turns": profile.max_turns,
        }
        self._emit("meta", self._static_meta)

    def metadata(self) -> dict[str, Any]:
        """Static run metadata plus dynamic `is_running` flag."""
        return {**self._static_meta, "is_running": self.is_running()}

    # ── private run loop ─────────────────────────────────────────────────

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
