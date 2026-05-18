"""DAO for the http_services table — the canonical HTTP service inventory."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class HttpService:
    subdomain: str
    scheme: str
    port: int
    url: str
    status_code: int | None
    title: str | None
    server: str | None
    technologies: tuple[str, ...]
    redirect_to: str | None
    tls_summary: str | None
    observed_at: str
    last_run_id: str
    in_scope_at_observation: bool


def upsert_service(conn: sqlite3.Connection, s: HttpService) -> None:
    """Replace the row for ``(subdomain, scheme, port)`` with ``s``."""
    conn.execute(
        "INSERT INTO http_services "
        "(subdomain, scheme, port, url, status_code, title, server, "
        " technologies, redirect_to, tls_summary, observed_at, last_run_id, "
        " in_scope_at_observation) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(subdomain, scheme, port) DO UPDATE SET "
        "url=excluded.url, status_code=excluded.status_code, "
        "title=excluded.title, server=excluded.server, "
        "technologies=excluded.technologies, redirect_to=excluded.redirect_to, "
        "tls_summary=excluded.tls_summary, observed_at=excluded.observed_at, "
        "last_run_id=excluded.last_run_id, "
        "in_scope_at_observation=excluded.in_scope_at_observation",
        (
            s.subdomain, s.scheme, s.port, s.url, s.status_code,
            s.title, s.server, json.dumps(list(s.technologies)),
            s.redirect_to, s.tls_summary, s.observed_at, s.last_run_id,
            1 if s.in_scope_at_observation else 0,
        ),
    )
    conn.commit()


def services_for_subdomains(
    conn: sqlite3.Connection, subdomains: Iterable[str]
) -> list[HttpService]:
    """Return all `http_services` rows for the given subdomains, in stable order."""
    sd_list = list(subdomains)
    if not sd_list:
        return []
    placeholders = ",".join("?" * len(sd_list))
    cursor = conn.execute(
        "SELECT subdomain, scheme, port, url, status_code, title, server, "
        "technologies, redirect_to, tls_summary, observed_at, last_run_id, "
        "in_scope_at_observation "
        f"FROM http_services WHERE subdomain IN ({placeholders}) "
        "ORDER BY subdomain, scheme, port",
        sd_list,
    )
    return [_row_to_service(row) for row in cursor]


def pick_canonical_service(rows: list[HttpService]) -> HttpService | None:
    """Return the best service from a list: HTTPS:443 > highest status > most recent.

    Used by triage to pick a representative service row for a finding's evidence
    context. Returns None for an empty list.
    """
    if not rows:
        return None
    # First sort by recency (newest first) — string sort on ISO-8601 is chronological.
    by_recency = sorted(rows, key=lambda r: r.observed_at, reverse=True)
    # Then stable-sort by the primary keys; equal keys preserve recency order.
    by_priority = sorted(by_recency, key=lambda r: (
        0 if (r.scheme == "https" and r.port == 443) else 1,
        -(r.status_code or 0),
    ))
    return by_priority[0]


def _row_to_service(row: tuple) -> HttpService:  # type: ignore[type-arg]
    return HttpService(
        subdomain=row[0], scheme=row[1], port=row[2], url=row[3],
        status_code=row[4], title=row[5], server=row[6],
        technologies=tuple(json.loads(row[7])),
        redirect_to=row[8], tls_summary=row[9],
        observed_at=row[10], last_run_id=row[11],
        in_scope_at_observation=bool(row[12]),
    )
