from __future__ import annotations

import time

from earn_money.agent.roe_profile import RoeProfile


class BudgetExceeded(Exception):
    pass


class RequestBudget:
    def __init__(self, profile: RoeProfile) -> None:
        self._max_turns = profile.max_turns
        self._max_requests = profile.max_requests
        self._max_posts = profile.max_posts
        self._max_response_bytes = profile.max_response_bytes
        self._max_runtime_seconds = profile.max_runtime_seconds
        self._delay_ms = profile.delay_between_requests_ms

        self._requests = 0
        self._posts = 0
        self._start = time.monotonic()

    # ── checks (raise on violation) ──────────────────────────────────────────

    def check_turn(self, turn: int) -> None:
        if turn > self._max_turns:
            raise BudgetExceeded(f"Turn {turn} exceeds max_turns {self._max_turns}")
        elapsed = time.monotonic() - self._start
        if elapsed > self._max_runtime_seconds:
            raise BudgetExceeded(
                f"Runtime {elapsed:.1f}s exceeds max_runtime_seconds {self._max_runtime_seconds}"
            )

    def check_request(self, method: str) -> None:
        if self._requests >= self._max_requests:
            raise BudgetExceeded(
                f"Request count {self._requests} at max_requests {self._max_requests}"
            )
        if method.upper() == "POST" and self._posts >= self._max_posts:
            raise BudgetExceeded(
                f"POST count {self._posts} at max_posts {self._max_posts}"
            )

    # ── recording ────────────────────────────────────────────────────────────

    def record_request(self, method: str) -> None:
        self._requests += 1
        if method.upper() == "POST":
            self._posts += 1

    def truncate_body(self, body: str) -> str:
        encoded = body.encode("utf-8", errors="replace")
        if len(encoded) <= self._max_response_bytes:
            return body
        return encoded[: self._max_response_bytes].decode("utf-8", errors="replace")

    def sleep_if_needed(self) -> None:
        if self._delay_ms > 0:
            time.sleep(self._delay_ms / 1000.0)

    # ── readonly properties for tests ────────────────────────────────────────

    @property
    def request_count(self) -> int:
        return self._requests

    @property
    def post_count(self) -> int:
        return self._posts
