"""Provider-call helpers (response-format fallback + per-model skiplist).

Extracted from hacker_loop.py to keep that module under the project's
200-line file cap. Importers in tests still see
`_call_provider_with_rf_fallback` via the `hacker_loop` facade.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from earn_money.agent.task_router import RouterUnconfigured, TaskType, resolve_model

log = logging.getLogger("earn_money.agent.hacker_loop")

_DEFAULT_DISABLE_RF_MODELS = "qwen/qwen3-235b-a22b"


def _disabled_rf_models() -> set[str]:
    """Per-model compatibility list for `response_format={"type":"json_object"}`.

    Some OpenRouter model adapters currently produce less reliable JSON
    when `response_format=json_object` is sent. For exact model IDs in
    this set we omit the kwarg entirely and rely on prompt phrasing +
    application-side validation (`parse_action_with_recovery` and the
    pydantic action schemas).

    Read per-call so tests can monkeypatch the env var. Matching is
    exact-string (no prefix / substring); add suffix variants like
    `:free` explicitly if their adapter has the same issue.

    Comma-separated. Default: `qwen/qwen3-235b-a22b` based on a
    2026-05-17 juice-shop probe walk where attempt-1-with-rf produced
    garbage on every observed turn.
    """
    raw = os.environ.get(
        "LLM_DISABLE_RESPONSE_FORMAT_MODELS", _DEFAULT_DISABLE_RF_MODELS,
    )
    return {m.strip() for m in raw.split(",") if m.strip()}


def _call_provider_with_rf_fallback(
    provider: Any, *, system: str, user: str, task: TaskType,
    with_response_format: bool,
) -> tuple[str | None, bool]:
    """Call provider.complete, returning (raw, used_response_format).

    When `with_response_format=True`, tries with `response_format={"type":
    "json_object"}` first; on provider exception, retries without it.
    When False, makes a single call without the kwarg. The kwarg is
    OMITTED on retries (not passed as None) since some OpenAI-compat
    providers treat None and omit differently.

    Models listed in `LLM_DISABLE_RESPONSE_FORMAT_MODELS` (see
    `_disabled_rf_models`) skip the response_format call entirely.
    """
    try:
        model = resolve_model(task)
    except RouterUnconfigured:
        model = None

    if with_response_format and model is not None and model in _disabled_rf_models():
        log.info(
            "model=%s response_format=disabled reason=model_skiplist",
            model,
        )
        with_response_format = False

    if with_response_format:
        try:
            raw = provider.complete(
                system=system, user=user, task=task,
                response_format={"type": "json_object"},
            )
            return raw, True
        except Exception as e:
            # Retry without response_format only when the model itself
            # rejected the structured-output kwarg (HTTP 400). Auth/credit/
            # rate-limit/provider-unavailable/timeout failures aren't
            # fixable by dropping the kwarg — bubble up as a clean failure.
            status = getattr(e, "status_code", None)
            if status != 400:
                log.error(
                    "Provider error (no retry): model=%s task=%s status=%s err=%s",
                    model or "?", task, status, e,
                )
                return None, False
            log.warning(
                "Provider rejected response_format (400); retrying without: %s", e,
            )
    try:
        return provider.complete(system=system, user=user, task=task), False
    except Exception as e:
        log.error(
            "Provider error: model=%s task=%s status=%s err=%s",
            model or "?", task,
            getattr(e, "status_code", None), e,
        )
        return None, False
