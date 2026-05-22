"""Reset-form discovery for stub 2.5.

GET the target base URL, run `discover_forms`, pick the first form
whose `flow_hint == "password_reset"`. If none, also probe the
bounded `candidate_reset_paths()` set.
"""
from __future__ import annotations

from dataclasses import dataclass

from httpx import Client, RequestError

from apps.stubs._shared.auth.endpoints import candidate_reset_paths
from apps.stubs._shared.auth.forms import AuthForm, discover_forms


_DEFAULT_TIMEOUT = 10.0


@dataclass(frozen=True)
class DiscoveryOutcome:
    form: AuthForm | None
    final_url: str
    error: str | None


def fetch_and_find_reset_form(base_url: str) -> DiscoveryOutcome:
    """Try the base URL first; fall back to bounded candidate
    paths if no reset form is found there."""
    try:
        with Client(timeout=_DEFAULT_TIMEOUT, follow_redirects=True) as client:
            home = client.get(base_url)
    except RequestError as exc:
        return DiscoveryOutcome(
            form=None, final_url=base_url, error=type(exc).__name__,
        )
    home_url = str(home.url)
    form = _find_reset_form(
        body=home.text or "", base=home_url,
        content_type=str(home.headers.get("content-type", "")),
    )
    if form is not None:
        return DiscoveryOutcome(form=form, final_url=home_url, error=None)

    # Fallback: bounded GETs to common reset paths.
    for path in candidate_reset_paths():
        candidate_url = home_url.rstrip("/") + path
        try:
            with Client(
                timeout=_DEFAULT_TIMEOUT, follow_redirects=True,
            ) as client:
                resp = client.get(candidate_url)
        except RequestError:
            continue
        form = _find_reset_form(
            body=resp.text or "", base=str(resp.url),
            content_type=str(resp.headers.get("content-type", "")),
        )
        if form is not None:
            return DiscoveryOutcome(
                form=form, final_url=str(resp.url), error=None,
            )

    return DiscoveryOutcome(form=None, final_url=home_url, error=None)


def _find_reset_form(
    *, body: str, base: str, content_type: str,
) -> AuthForm | None:
    forms = discover_forms(body, base, response_content_type=content_type)
    for f in forms:
        if f.flow_hint == "password_reset":
            return f
    return None
