"""HackerOne API client. Scope-fetch only in Phase 1."""

from __future__ import annotations

import httpx

_BASE_URL = "https://api.hackerone.com/v1"


class HackerOneAPIError(Exception):
    """Raised on HTTP failure or missing credentials."""


class Client:
    def __init__(
        self,
        *,
        username: str,
        token: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 20.0,
    ) -> None:
        if not username or not token:
            raise HackerOneAPIError(
                "HackerOne credentials missing — set HACKERONE_API_USERNAME "
                "and HACKERONE_API_TOKEN."
            )
        self._client = httpx.Client(
            base_url=_BASE_URL,
            auth=(username, token),
            headers={"Accept": "application/json"},
            transport=transport,
            timeout=timeout,
        )

    def fetch_structured_scope(self, handle: str) -> tuple[list[str], list[str]]:
        """Return (in_scope, out_of_scope) asset identifiers for a program handle."""
        response = self._client.get(f"/hackers/programs/{handle}/structured_scopes")
        if response.status_code != 200:
            raise HackerOneAPIError(
                f"HackerOne API returned {response.status_code} for {handle}: "
                f"{response.text}"
            )
        in_scope: list[str] = []
        out_of_scope: list[str] = []
        for item in response.json().get("data", []):
            attrs = item.get("attributes") or {}
            asset = attrs.get("asset_identifier")
            if not asset:
                continue
            if attrs.get("eligible_for_submission"):
                in_scope.append(asset)
            else:
                out_of_scope.append(asset)
        return in_scope, out_of_scope

    def close(self) -> None:
        self._client.close()
