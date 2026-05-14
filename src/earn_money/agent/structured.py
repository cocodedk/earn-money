"""Structured-output request helper (spec §5).

`request_structured(provider, *, system, user, schema, task)` asks the
LLM for JSON matching `schema`, parses the reply, runs the application
validator, and — on failure — issues exactly one repair prompt that
includes the validator's error and the schema again.

Two paths under the hood:

- If the provider supports `response_format` (OpenAI / OpenRouter on a
  capable model), the schema is passed natively. The reply will *very
  often* be valid JSON but we still validate, per spec.
- If the provider doesn't, we fall back to a JSON-only instruction
  prepended to the user message + app-side parsing. Same retry budget.

The helper never trusts the model just because a schema was requested.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from earn_money.agent.providers import Provider
from earn_money.agent.task_router import TaskType

_MAX_REPAIR_RETRIES = 1

ValidatorFn = Callable[[dict[str, Any]], None]


class StructuredOutputError(Exception):
    """Raised when the structured request can't yield a valid payload."""


def request_structured(
    provider: Provider,
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    task: str | TaskType | None = None,
    validator: ValidatorFn | None = None,
) -> dict[str, Any]:
    """Issue a JSON-only request. Returns the parsed object on success.

    `schema` is the OpenAI-style `{"name": ..., "schema": {...}}` block;
    we forward it via `response_format` when the provider supports it.
    `validator` runs on every reply — if it raises, we retry once with
    a repair prompt; if the repair also fails, we raise
    `StructuredOutputError` with the underlying validator error.
    """
    schema_block = _json_dumps(schema)
    enriched_system = _augment_system_prompt(system, schema_block)
    last_error: str | None = None
    last_payload: dict[str, Any] | None = None
    for attempt in range(_MAX_REPAIR_RETRIES + 1):
        prompt = _build_user_prompt(user, schema_block, attempt, last_error)
        reply = _call_with_response_format(
            provider, enriched_system, prompt, schema, task,
        )
        parsed = _try_parse_json(reply)
        if parsed is None:
            last_error = "reply was not valid JSON"
            continue
        if validator is None:
            return parsed
        try:
            validator(parsed)
        except Exception as exc:
            last_error = f"validation failed: {type(exc).__name__}: {exc}"
            last_payload = parsed
            continue
        return parsed
    raise StructuredOutputError(
        f"could not produce a schema-valid reply after "
        f"{_MAX_REPAIR_RETRIES + 1} attempts: {last_error or 'unknown'}; "
        f"last payload: "
        f"{json.dumps(last_payload, sort_keys=True) if last_payload else 'none'}",
    )


def _augment_system_prompt(system: str, schema_block: str) -> str:
    """Append a strict 'reply with JSON matching this schema' clause."""
    return (
        f"{system}\n\n"
        "When asked for a structured reply, return ONLY a single JSON "
        "object that matches the schema below. Do not wrap it in code "
        "fences or commentary. Do not add fields outside the schema.\n\n"
        f"Schema:\n{schema_block}"
    )


def _build_user_prompt(
    user: str, schema_block: str, attempt: int, last_error: str | None,
) -> str:
    if attempt == 0 or last_error is None:
        return user
    # Repair retry — be explicit about what failed last time.
    return (
        f"{user}\n\n"
        "Your previous reply failed validation with this error:\n"
        f"  {last_error}\n\n"
        "Reply again with ONLY a JSON object that matches the schema. "
        f"Schema:\n{schema_block}"
    )


def _call_with_response_format(
    provider: Provider,
    system: str,
    user: str,
    schema: dict[str, Any],
    task: str | TaskType | None,
) -> str:
    """Best-effort response_format passthrough."""
    response_format: dict[str, object] = {
        "type": "json_schema", "json_schema": schema,
    }
    try:
        return provider.complete(
            system=system, user=user, task=task,
            response_format=response_format,
        )
    except TypeError:
        # Defensive: a non-protocol provider may not accept the kwarg.
        return provider.complete(system=system, user=user, task=task)


def _try_parse_json(reply: str) -> dict[str, Any] | None:
    """Extract the first JSON object from the reply. Models often wrap
    JSON in fenced code blocks or trailing prose; the regex finds the
    outermost-looking brace pair."""
    match = re.search(r"\{.*\}", reply, re.DOTALL)
    if not match:
        return None
    try:
        loaded = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)
