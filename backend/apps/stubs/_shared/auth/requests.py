"""Probe-pair builder for Phase 2 comparison stubs.

`build_probe_pair()` constructs the two `httpx.Request` objects a
comparison stub fires per discovered auth form: one with a synthetic
invalid identifier, one with a scoped valid identifier (when the
stub has fixture-validated access to one).

Spec 2.1 §2.6 — shape preservation rules:
* Same HTTP method, parameter names, content type, header set
  (except dynamic cookies + per-request CSRF tokens), redirect
  policy, and User-Agent.
* Same generated bogus password in both probes so the difference is
  purely the identifier value.
* When the form carries CSRF / hidden inputs, the caller passes
  ``csrf_refresh`` so each probe gets fresh hidden values from a
  fresh GET. CSRF re-use voids the comparison.

This helper builds Request objects only. Scope, RoE, rate-limit,
and active-safety gates all run BEFORE the runner calls httpx.
Cookie-jar isolation is enforced at execution time (the runner
fires each request with a fresh `httpx.Client()`); see
[shared-infra B](../../../docs/superpowers/plans/2026-05-21-phase-2-authentication/shared-infra/B-request-shape.md).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from .forms import AuthForm


SCANNER_USER_AGENT = "cookbook-scanner/v2 (+https://cocode.dk)"


@dataclass(frozen=True)
class ProbePair:
    """Matched invalid + valid control requests, built from one
    `AuthForm`. ``valid_request`` is None when no scoped valid
    identifier is available — the stub then runs invalid-only and
    must mark any Finding as `candidate`/`low` per spec 2.1 §6."""
    form: AuthForm
    invalid_request: httpx.Request
    valid_request: httpx.Request | None


def build_probe_pair(
    *,
    form: AuthForm,
    invalid_identifier: str,
    valid_identifier: str | None,
    bogus_password: str,
    csrf_refresh: Callable[[], dict[str, str]] | None = None,
) -> ProbePair:
    """Return a `ProbePair` for the given `AuthForm`.

    The two requests share method, parameter names, content type,
    User-Agent, and the bogus password; only the identifier value
    differs. When ``csrf_refresh`` is supplied, it is called once per
    request to inject fresh hidden values; otherwise the hidden
    values from ``form.hidden_fields`` are reused.
    """
    invalid_request = _build_request(
        form=form, identifier_value=invalid_identifier,
        bogus_password=bogus_password, csrf_refresh=csrf_refresh,
    )
    if valid_identifier is None:
        valid_request = None
    else:
        valid_request = _build_request(
            form=form, identifier_value=valid_identifier,
            bogus_password=bogus_password, csrf_refresh=csrf_refresh,
        )
    return ProbePair(
        form=form,
        invalid_request=invalid_request,
        valid_request=valid_request,
    )


def _build_request(
    *,
    form: AuthForm,
    identifier_value: str,
    bogus_password: str,
    csrf_refresh: Callable[[], dict[str, str]] | None,
) -> httpx.Request:
    """Construct one httpx.Request that matches the form's shape."""
    hidden = csrf_refresh() if csrf_refresh is not None else dict(form.hidden_fields)
    payload: dict[str, str] = {}
    if form.identifier_field is not None:
        payload[form.identifier_field] = identifier_value
    if form.password_field is not None:
        payload[form.password_field] = bogus_password
    payload.update(hidden)
    headers = {
        "user-agent": SCANNER_USER_AGENT,
        "content-type": form.content_type,
    }
    return httpx.Request(
        method=form.method,
        url=form.action_url,
        data=payload,
        headers=headers,
    )
