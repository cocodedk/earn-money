"""RoE-aware finding verifier.

Turns observations into candidate or verified findings for:
- IDOR
- Debug / actuator endpoints
- Token leaks
- Unsafe redirects
"""
from __future__ import annotations

import re
from typing import Any

from earn_money.agent.hacker_session import HackerSession
from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.roe_profile import RoeProfile

_USER_FIELDS = re.compile(r"\b(email|role|user_id|username|id)\b", re.IGNORECASE)
_DEBUG_PATHS = re.compile(
    r"/(debug|actuator|env|phpinfo|server-status|health|metrics|trace|dump)(/|$)",
    re.IGNORECASE,
)
_ENV_MARKERS = re.compile(
    r"\b(JAVA_HOME|PATH=|DB_|SECRET|PASSWORD|API_KEY|stack_trace|StackTrace|exception)\b"
)
_TOKEN_PATTERN = re.compile(
    r"\b(eyJ[A-Za-z0-9_\-]{10,}|[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{20,})\b"
)
_NUMERIC_ID = re.compile(r"/\d+$")
_REDIRECT_PARAMS = re.compile(r"[?&](next|redirect|url|return|to)=", re.IGNORECASE)


def _mask(value: str) -> str:
    return value[:4] + "***" if len(value) > 4 else "***"


class FindingVerifier:
    def __init__(self, profile: RoeProfile) -> None:
        self._p = profile

    def evaluate(
        self,
        action: dict[str, Any],
        observation: ObservationWrapper,
        session: HackerSession,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        candidates: list[dict[str, Any]] = []
        verified: list[dict[str, Any]] = []

        for fn in (
            self._check_idor,
            self._check_debug_endpoint,
            self._check_token_leak,
            self._check_unsafe_redirect,
        ):
            c, v = fn(action, observation, session)
            candidates.extend(c)
            verified.extend(v)

        return candidates, verified

    # ── individual checks ─────────────────────────────────────────────────────

    def _check_idor(
        self,
        action: dict[str, Any],
        obs: ObservationWrapper,
        session: HackerSession,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        path = action.get("args", {}).get("path", "")
        if action.get("tool") != "get":
            return [], []
        if obs.status != 200:
            return [], []
        if not _NUMERIC_ID.search(path):
            return [], []
        if not _USER_FIELDS.search(obs.body):
            return [], []

        candidate = {"type": "idor", "path": path, "status": obs.status}

        # Promote to verified when we have enough evidence
        active_id = session.ids.get("user_id") or session.ids.get("active_user_id")
        requested_id = _NUMERIC_ID.search(path)
        if (
            self._p.allow_idor_checks
            and active_id
            and requested_id
            and requested_id.group().lstrip("/") != active_id
            and _USER_FIELDS.search(obs.body)
            and self._p.require_replay_steps
        ):
            replay = f"GET {path} while authenticated as user {active_id}"
            verified = {**candidate, "confirmed": True, "replay": replay}
            return [], [verified]

        return [candidate], []

    def _check_debug_endpoint(
        self,
        action: dict[str, Any],
        obs: ObservationWrapper,
        _session: HackerSession,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        path = action.get("args", {}).get("path", "")
        if obs.status != 200:
            return [], []
        if not _DEBUG_PATHS.search(path):
            return [], []
        if not _ENV_MARKERS.search(obs.body):
            return [], []
        candidate = {"type": "debug_endpoint", "path": path, "status": obs.status}
        return [candidate], []

    def _check_token_leak(
        self,
        action: dict[str, Any],
        obs: ObservationWrapper,
        _session: HackerSession,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        matches = _TOKEN_PATTERN.findall(obs.body)
        if not matches:
            return [], []
        path = action.get("args", {}).get("path", "")
        masked = [_mask(m) for m in matches]
        candidate = {"type": "token_leak", "path": path, "tokens_masked": masked}
        return [candidate], []

    def _check_unsafe_redirect(
        self,
        action: dict[str, Any],
        obs: ObservationWrapper,
        _session: HackerSession,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        path = action.get("args", {}).get("path", "")
        if not _REDIRECT_PARAMS.search(path):
            return [], []
        location = obs.headers.get("location", "")
        if not location:
            return [], []
        candidate = {
            "type": "unsafe_redirect",
            "path": path,
            "location": location,
        }
        return [candidate], []
