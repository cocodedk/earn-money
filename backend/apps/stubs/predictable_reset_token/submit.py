"""Reset-request submit for stub 2.5.

Build the password-reset POST payload from an `AuthForm` and the
canary email, fire it via httpx, return True/False for success
(2xx / 3xx). Transport errors return False so the runner can
break its sampling loop.
"""
from __future__ import annotations

from httpx import Client, RequestError

from apps.stubs._shared.auth.forms import AuthForm
from apps.stubs._shared.auth.requests import SCANNER_USER_AGENT


_DEFAULT_TIMEOUT = 10.0


def request_reset(*, form: AuthForm, identifier_value: str) -> bool:
    """Submit one password-reset POST. Returns True when the
    target accepted the request (2xx or 3xx), False on 4xx / 5xx
    / transport error."""
    payload: dict[str, str] = dict(form.hidden_fields)
    if form.identifier_field is not None:
        payload[form.identifier_field] = identifier_value
    headers = {
        "user-agent": SCANNER_USER_AGENT,
        "content-type": form.content_type,
    }
    try:
        with Client(
            timeout=_DEFAULT_TIMEOUT,
            follow_redirects=False,
        ) as client:
            resp = client.request(
                form.method, form.action_url,
                data=payload, headers=headers,
            )
    except RequestError:
        return False
    return 200 <= resp.status_code < 400
