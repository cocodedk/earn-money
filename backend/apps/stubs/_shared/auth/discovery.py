"""Passive discovery fetch with bounded scope-aware redirect following.

`fetch_for_discovery()` does one GET of the target's base URL with
no credentials. Redirects are handled manually so each hop's URL
is run through `enforce_scope` BEFORE the next request goes out —
otherwise httpx would silently fetch off-scope hosts when an
in-scope target redirects to an SSO/IdP host (`P1` finding from
codex review on commit aac1efb).

Lifted from `username_enum/` to `_shared/auth/` when stub 2.3
became the second consumer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import httpx
from httpx import Client

from apps.programs.exceptions import OutOfScope
from apps.programs.loader import Program
from apps.stubs._shared.scope_check import enforce_scope


_DEFAULT_TIMEOUT = 10.0
_MAX_REDIRECTS = 3
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


@dataclass(frozen=True)
class FetchOutcome:
    """Result of the discovery GET. `body` is the response text (empty
    on transport error). `content_type` is the bare media type with no
    charset parameter. `error` distinguishes transport failures (e.g.,
    `ConnectError`) from scope refusals (`redirect_off_scope`)."""
    ok: bool
    status: int
    body: str
    content_type: str
    final_url: str
    error: str | None


def fetch_for_discovery(
    base_url: str,
    *,
    target: Any,
    program: Program,
    scan_run: Any = None,
    stub_id: str | None = None,
    max_redirects: int = _MAX_REDIRECTS,
) -> FetchOutcome:
    """GET ``base_url`` with bounded scope-aware redirect following.

    The original target host is already in-scope per scan pre-flight;
    redirects beyond that are scope-checked before each fetch. An
    off-scope redirect target emits `OUT_OF_SCOPE_REJECTED` once and
    returns a `redirect_off_scope` outcome — the off-scope GET is
    never issued.
    """
    current_url = base_url
    for hop in range(max_redirects + 1):
        if hop > 0:
            try:
                enforce_scope(
                    target, current_url, program,
                    scan_run=scan_run, stub_id=stub_id,
                )
            except OutOfScope:
                return FetchOutcome(
                    ok=False, status=0, body="", content_type="",
                    final_url=current_url, error="redirect_off_scope",
                )
        try:
            with Client(
                timeout=_DEFAULT_TIMEOUT, follow_redirects=False,
            ) as client:
                response = client.get(current_url)
        except httpx.RequestError as exc:
            return FetchOutcome(
                ok=False, status=0, body="", content_type="",
                final_url=current_url, error=type(exc).__name__,
            )
        location = response.headers.get("location")
        if response.status_code in _REDIRECT_STATUSES and location:
            current_url = urljoin(current_url, location)
            continue
        content_type = str(
            response.headers.get("content-type", "")
        ).split(";")[0].strip()
        return FetchOutcome(
            ok=True,
            status=response.status_code,
            body=response.text or "",
            content_type=content_type,
            final_url=str(response.url),
            error=None,
        )
    return FetchOutcome(
        ok=False, status=0, body="", content_type="",
        final_url=current_url, error="too_many_redirects",
    )
