"""Chaos public DNS API client."""

from __future__ import annotations

import httpx

_BASE_URL = "https://dns.projectdiscovery.io"


class ChaosAPIError(Exception):
    """Raised on HTTP failure or missing credentials."""


class Client:
    def __init__(
        self,
        *,
        token: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 20.0,
    ) -> None:
        if not token:
            raise ChaosAPIError(
                "Chaos credentials missing — set CHAOS_API_TOKEN."
            )
        self._client = httpx.Client(
            base_url=_BASE_URL,
            headers={"Authorization": token, "Accept": "application/json"},
            transport=transport,
            timeout=timeout,
        )

    def fetch_subdomains(self, domain: str) -> list[str]:
        """Return Chaos-known FQDNs for ``domain``. Deduped and lowercased."""
        try:
            response = self._client.get(f"/dns/{domain}/subdomains")
        except httpx.RequestError as exc:
            raise ChaosAPIError(
                f"Network error fetching {domain}: {exc}"
            ) from exc
        if response.status_code != 200:
            raise ChaosAPIError(
                f"Chaos API returned {response.status_code} for {domain}: "
                f"{response.text}"
            )
        data = response.json()
        seen: set[str] = set()
        out: list[str] = []
        for sub in data.get("subdomains", []):
            fqdn = f"{sub}.{domain}".lower()
            if fqdn not in seen:
                seen.add(fqdn)
                out.append(fqdn)
        return out

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
