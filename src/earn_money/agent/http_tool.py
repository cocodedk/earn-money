"""RoE-aware HTTP tool that wraps every response as an ObservationWrapper."""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from earn_money.agent.budget import RequestBudget
from earn_money.agent.observations import ObservationWrapper
from earn_money.agent.roe_policy import RoePolicy
from earn_money.agent.scope_policy import ScopePolicy

log = logging.getLogger(__name__)

_ALLOWED_HEADERS = frozenset(["authorization", "cookie", "x-api-key", "content-type"])


@dataclass
class HttpResult:
    status: int
    body: str
    headers: dict[str, str]
    final_url: str | None = None


class HttpTool:
    def __init__(
        self,
        base_url: str,
        roe_policy: RoePolicy,
        scope_policy: ScopePolicy,
        budget: RequestBudget,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.roe_policy = roe_policy
        self.scope_policy = scope_policy
        self.budget = budget
        self.session_headers: dict[str, str] = {}

    # ── public API ────────────────────────────────────────────────────────────

    def get(self, path: str, params: dict[str, str] | None = None) -> ObservationWrapper:
        decision = self.roe_policy.decide("http_get")
        if not decision.allowed:
            raise PermissionError(decision.reason)
        url = self.scope_policy.check(path)
        self.budget.check_request("GET")
        result = self._send("GET", url, params=params)
        self.budget.record_request("GET")
        log.info("GET %s → %s", url, result.status)
        return self._wrap(result)

    def post(
        self,
        path: str,
        json_body: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
    ) -> ObservationWrapper:
        decision = self.roe_policy.decide("http_post")
        if not decision.allowed:
            raise PermissionError(decision.reason)
        url = self.scope_policy.check(path)
        self.budget.check_request("POST")
        result = self._send("POST", url, json_body=json_body, data=data)
        self.budget.record_request("POST")
        log.info("POST %s → %s", url, result.status)
        return self._wrap(result)

    def set_header(self, name: str, value: str) -> None:
        if name.lower() not in _ALLOWED_HEADERS:
            raise ValueError(f"Header {name!r} not in allowed list")
        self.session_headers[name] = value

    def decode_jwt(self, token: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise ValueError("JWT must have 3 parts")
            def _b64(s: str) -> dict[str, Any]:
                padded = s + "=" * (4 - len(s) % 4)
                return json.loads(base64.urlsafe_b64decode(padded))  # type: ignore[no-any-return]
            return _b64(parts[0]), _b64(parts[1])
        except Exception as e:
            raise ValueError(f"Invalid JWT: {e}") from e

    # ── private ───────────────────────────────────────────────────────────────

    def _send(
        self,
        method: str,
        url: str,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
    ) -> HttpResult:
        headers = {**self.session_headers}
        with httpx.Client(follow_redirects=False) as client:
            resp = client.request(
                method,
                url,
                params=params,
                json=json_body,
                data=data,
                headers=headers,
            )
            final_url = str(resp.url)

            # Manual redirect validation
            if resp.is_redirect:
                loc = resp.headers.get("location", "")
                final_url = self.scope_policy.check_redirect(loc, url)
                resp2 = client.request(method, final_url, headers=headers)
                return HttpResult(
                    status=resp2.status_code,
                    body=self.budget.truncate_body(resp2.text),
                    headers=dict(resp2.headers),
                    final_url=str(resp2.url),
                )

            return HttpResult(
                status=resp.status_code,
                body=self.budget.truncate_body(resp.text),
                headers=dict(resp.headers),
                final_url=final_url,
            )

    def _wrap(self, result: HttpResult) -> ObservationWrapper:
        return ObservationWrapper.from_response(
            status=result.status,
            final_url=result.final_url or self.base_url,
            all_headers=result.headers,
            body=result.body,
        )
