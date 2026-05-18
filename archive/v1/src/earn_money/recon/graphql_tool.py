"""GraphQL introspection probe.

For a base URL, try common GraphQL paths (`/graphql`, `/api/graphql`,
…), POST a minimal introspection query, and emit a Signal when the
response contains `data.__schema` — i.e. introspection is enabled
in production and the schema is publicly enumerable.

Detection only — we never dump the full schema. The operator pulls
it by hand for the report once they decide the finding is real.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from earn_money.recon.signals import Signal

InScope = Callable[[str], bool]

# Conservative breadth: covers ~95 % of real-world introspection
# endpoints we'd want to flag. Anything wilder belongs in katana.
COMMON_PATHS: tuple[str, ...] = (
    "/graphql",
    "/api/graphql",
    "/v1/graphql",
    "/v2/graphql",
    "/query",
    "/api/v1/graphql",
)

# Minimal introspection — just enough to confirm `__schema` resolves.
# A full IntrospectionQuery is verbose; we only need to detect, not dump.
_INTROSPECTION_QUERY = (
    "{ __schema { queryType { name } types { name } } }"
)


def build_query() -> dict[str, str]:
    """Return the POST body for the minimal introspection query."""
    return {"query": _INTROSPECTION_QUERY}


def _host_of(url: str) -> str:
    return urlparse(url).hostname or ""


def _parse_schema(body: str) -> dict[str, Any] | None:
    """Return the `__schema` dict if the response is valid GraphQL JSON
    with introspection enabled. None for any failure mode."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    payload = data.get("data")
    if not isinstance(payload, dict):
        return None
    schema = payload.get("__schema")
    if isinstance(schema, dict) and schema.get("types"):
        return schema
    return None


def _signal_for_introspection(
    endpoint_url: str,
    schema: dict[str, Any],
    *,
    run_id: str,
    observed_at: str,
) -> Signal:
    types = schema.get("types") or []
    type_names = [
        t.get("name") for t in types
        if isinstance(t, dict) and isinstance(t.get("name"), str)
    ][:10]
    query_type = (schema.get("queryType") or {}).get("name") or "Query"
    payload = json.dumps(
        {
            "severity": "medium",
            "endpoint": endpoint_url,
            "query_type": query_type,
            "type_sample": type_names,
        },
        sort_keys=True,
    )
    parsed_path = urlparse(endpoint_url).path or "/"
    return Signal(
        run_id=run_id,
        tool="graphql-probe",
        signal_type="introspection_enabled",
        asset=_host_of(endpoint_url),
        target=endpoint_url,
        signature=f"graphql|{parsed_path}|introspection",
        payload=payload,
        observed_at=observed_at,
    )


def probe(
    base_url: str,
    *,
    client: httpx.Client,
    in_scope: InScope,
    run_id: str,
    observed_at: str,
    paths: tuple[str, ...] = COMMON_PATHS,
) -> list[Signal]:
    """POST a minimal introspection query at every common GraphQL path.

    Emits one Signal per path that returns a valid \\__schema response.
    Same-scope re-check is mandatory — the runner passes its live-scope
    predicate; we never trust a URL without it.
    """
    base_host = _host_of(base_url)
    if not in_scope(base_host):
        return []

    out: list[Signal] = []
    body = build_query()
    for path in paths:
        endpoint = urljoin(base_url, path)
        if not in_scope(_host_of(endpoint)):
            continue
        try:
            resp = client.post(endpoint, json=body)
        except httpx.HTTPError:
            continue
        if resp.status_code != 200:
            continue
        schema = _parse_schema(resp.text)
        if schema is None:
            continue
        out.append(
            _signal_for_introspection(
                endpoint, schema,
                run_id=run_id, observed_at=observed_at,
            )
        )
    return out
