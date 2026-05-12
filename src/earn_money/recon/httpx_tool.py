"""Subprocess wrapper around the ProjectDiscovery ``httpx`` CLI.

Not to be confused with the Python ``httpx`` library — this module
shells out to the binary. Parsing is forgiving: a malformed line is
logged-and-skipped rather than abort the parse."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from earn_money.recon.services import HttpService


def build_command(targets: Sequence[str]) -> list[str]:
    """Return argv for an httpx invocation with the given targets.

    Targets are passed via comma-separated -u rather than stdin so the
    batch wrapper (which doesn't pipe stdin) can invoke us directly.
    For ~50 targets per batch, argv stays well bounded.
    """
    if not targets:
        raise ValueError("build_command requires at least one target")
    return [
        "httpx",
        "-u", ",".join(targets),
        "-silent",
        "-json",
        "-no-follow-redirects",
        "-status-code",
        "-title",
        "-tech-detect",
        "-tls-grab",
        "-web-server",
    ]


def parse_jsonl(
    raw: str, *, run_id: str, observed_at: str
) -> list[HttpService]:
    """Parse the JSONL output of httpx into HttpService rows. Lines
    that don't decode are silently skipped — the runner counts them
    via parse_failures separately if it cares."""
    services: list[HttpService] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            services.append(_to_service(data, run_id=run_id, observed_at=observed_at))
        except (KeyError, ValueError):
            continue
    return services


def _to_service(
    data: dict[str, Any], *, run_id: str, observed_at: str
) -> HttpService:
    techs = tuple(data.get("tech") or ())
    tls = data.get("tls") or {}
    location = data.get("location") or None
    return HttpService(
        subdomain=str(data["host"]),
        scheme=str(data["scheme"]),
        port=int(data["port"]),
        url=str(data["url"]),
        status_code=int(data["status_code"]) if "status_code" in data else None,
        title=(data.get("title") or None),
        server=(data.get("webserver") or None),
        technologies=techs,
        redirect_to=location,
        tls_summary=json.dumps(tls) if tls else None,
        observed_at=observed_at,
        last_run_id=run_id,
        in_scope_at_observation=True,
    )
