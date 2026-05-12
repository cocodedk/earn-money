from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from earn_money import db
from earn_money.recon import services


def _conn(tmp_path: Path) -> sqlite3.Connection:
    return db.open_db(tmp_path / "test.sqlite")


def test_upsert_inserts_first_observation(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    obs = services.HttpService(
        subdomain="api.example.com", scheme="https", port=443,
        url="https://api.example.com/", status_code=200,
        title="Example API", server="nginx",
        technologies=("nginx", "openresty"),
        redirect_to=None, tls_summary='{"issuer":"LE"}',
        observed_at="2026-05-12T08:00:00Z", last_run_id="r1",
        in_scope_at_observation=True,
    )
    services.upsert_service(conn, obs)
    row = conn.execute(
        "SELECT subdomain, scheme, port, status_code, technologies "
        "FROM http_services"
    ).fetchone()
    assert row[:4] == ("api.example.com", "https", 443, 200)
    assert json.loads(row[4]) == ["nginx", "openresty"]


def test_upsert_replaces_existing_row_for_same_key(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    first = services.HttpService(
        subdomain="api.example.com", scheme="https", port=443,
        url="https://api.example.com/", status_code=200, title=None,
        server="nginx", technologies=(),
        redirect_to=None, tls_summary=None,
        observed_at="2026-05-12T08:00:00Z", last_run_id="r1",
        in_scope_at_observation=True,
    )
    services.upsert_service(conn, first)
    second = services.HttpService(
        **{**first.__dict__, "status_code": 503, "last_run_id": "r2",
           "observed_at": "2026-05-12T14:00:00Z"},
    )
    services.upsert_service(conn, second)
    rows = conn.execute(
        "SELECT status_code, last_run_id FROM http_services"
    ).fetchall()
    assert rows == [(503, "r2")]


def test_pick_canonical_service_prefers_https_443(tmp_path: Path) -> None:
    rows = [
        services.HttpService(
            subdomain="x", scheme="http", port=80,
            url="http://x/", status_code=200, title=None, server=None,
            technologies=(), redirect_to=None, tls_summary=None,
            observed_at="2026-01-01T00:00:00Z", last_run_id="r",
            in_scope_at_observation=True,
        ),
        services.HttpService(
            subdomain="x", scheme="https", port=443,
            url="https://x/", status_code=200, title=None, server=None,
            technologies=(), redirect_to=None, tls_summary=None,
            observed_at="2026-01-01T00:00:00Z", last_run_id="r",
            in_scope_at_observation=True,
        ),
    ]
    picked = services.pick_canonical_service(rows)
    assert picked is not None
    assert (picked.scheme, picked.port) == ("https", 443)


def test_pick_canonical_service_prefers_higher_status_on_same_scheme_port(tmp_path: Path) -> None:
    rows = [
        services.HttpService(
            subdomain="x", scheme="https", port=443,
            url="https://x/", status_code=200, title=None, server=None,
            technologies=(), redirect_to=None, tls_summary=None,
            observed_at="2026-01-01T00:00:00Z", last_run_id="r",
            in_scope_at_observation=True,
        ),
        services.HttpService(
            subdomain="x", scheme="https", port=443,
            url="https://x/", status_code=503, title=None, server=None,
            technologies=(), redirect_to=None, tls_summary=None,
            observed_at="2026-01-01T00:00:00Z", last_run_id="r",
            in_scope_at_observation=True,
        ),
    ]
    picked = services.pick_canonical_service(rows)
    assert picked is not None
    # The -(status_code or 0) key means LOWER (more negative) sorts FIRST.
    # 503 has -503 which is less than -200, so 503 wins.
    assert picked.status_code == 503


def test_pick_canonical_service_prefers_newest_on_other_ties(tmp_path: Path) -> None:
    """The bug-fix this test pins: when scheme/port/status all tie,
    the most recent observation wins. Was inverted in cycle 1."""
    rows = [
        services.HttpService(
            subdomain="x", scheme="https", port=443,
            url="https://x/", status_code=200, title=None, server=None,
            technologies=(), redirect_to=None, tls_summary=None,
            observed_at="2026-01-01T00:00:00Z", last_run_id="r1",
            in_scope_at_observation=True,
        ),
        services.HttpService(
            subdomain="x", scheme="https", port=443,
            url="https://x/", status_code=200, title=None, server=None,
            technologies=(), redirect_to=None, tls_summary=None,
            observed_at="2026-02-01T00:00:00Z", last_run_id="r2",
            in_scope_at_observation=True,
        ),
    ]
    picked = services.pick_canonical_service(rows)
    assert picked is not None
    assert picked.observed_at == "2026-02-01T00:00:00Z"
    assert picked.last_run_id == "r2"


def test_pick_canonical_service_empty_returns_none(tmp_path: Path) -> None:
    assert services.pick_canonical_service([]) is None


def test_pick_canonical_service_handles_none_status(tmp_path: Path) -> None:
    rows = [
        services.HttpService(
            subdomain="x", scheme="https", port=443,
            url="https://x/", status_code=None, title=None, server=None,
            technologies=(), redirect_to=None, tls_summary=None,
            observed_at="2026-01-01T00:00:00Z", last_run_id="r",
            in_scope_at_observation=True,
        ),
        services.HttpService(
            subdomain="x", scheme="https", port=443,
            url="https://x/", status_code=200, title=None, server=None,
            technologies=(), redirect_to=None, tls_summary=None,
            observed_at="2026-01-01T00:00:00Z", last_run_id="r",
            in_scope_at_observation=True,
        ),
    ]
    picked = services.pick_canonical_service(rows)
    assert picked is not None
    # status 200 beats None (which coerces to 0)
    assert picked.status_code == 200


def test_services_for_program_filters_by_subdomain(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    # Insert two subdomains; the test asks for one.
    for sd in ("api.example.com", "www.example.com"):
        services.upsert_service(conn, services.HttpService(
            subdomain=sd, scheme="https", port=443, url=f"https://{sd}/",
            status_code=200, title=None, server=None, technologies=(),
            redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="r", in_scope_at_observation=True,
        ))
    rows = services.services_for_subdomains(conn, ["api.example.com"])
    assert [s.subdomain for s in rows] == ["api.example.com"]
