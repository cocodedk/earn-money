"""`bin/verify-takeover <hash-prefix>` — ownership check for takeover findings.

Resolves a takeover-class finding, extracts the GitHub org/user name
from its signal payload (`payload.extracted`), and asks the GitHub API
whether the name is claimed. Prints a CLAIMED / UNCLAIMED / INDETERMINATE
verdict plus a suggested operator transition.

v1 supports github-takeover only. The `_github_user_lookup` indirection
exists so tests mock the network call cleanly; production hits
``https://api.github.com/users/<name>``.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import httpx

from earn_money import config, db


def _github_user_lookup(name: str) -> tuple[int, dict[str, Any]]:
    """Return (status, body). status=0 on network failure (indeterminate).

    Reads ``GITHUB_TOKEN`` from the environment when present and sends it
    as a Bearer token — the unauthenticated quota is 60 requests/hour
    per IP, low enough to hit on a busy day. 403 with the rate-limit
    headers set surfaces as status 429 + an error body so the caller
    can distinguish "rate-limited" from "actually-claimed-but-forbidden".
    """
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = httpx.get(
            f"https://api.github.com/users/{name}",
            timeout=10.0,
            headers=headers,
        )
    except httpx.HTTPError:
        return 0, {}
    if r.status_code == 200:
        try:
            return 200, r.json()
        except ValueError:
            return 200, {}
    if r.status_code == 403 and r.headers.get("X-RateLimit-Remaining") == "0":
        return 429, {
            "rate_limit_reset": r.headers.get("X-RateLimit-Reset", ""),
            "error": "GitHub API rate limit exhausted; set GITHUB_TOKEN to raise it.",
        }
    return r.status_code, {}


def _resolve_finding(
    conn: sqlite3.Connection, prefix: str,
) -> tuple[str, str, str, str] | None:
    """Return (finding_hash, vuln_class, asset, signal_payload) for a unique
    hash-prefix match, or None if missing/ambiguous (caller prints the error).

    Multiple signals can fire on the same (run_id, asset) when several
    templates match the same host — match on signature too so we pick
    the *correct* template's payload, not some other template's payload
    that happened to land on the same asset in the same run."""
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = conn.execute(
        "SELECT finding_hash, vuln_class, asset, source_run_id, signature "
        "FROM findings WHERE finding_hash LIKE ? ESCAPE '\\' "
        "ORDER BY finding_hash",
        (escaped + "%",),
    ).fetchall()
    if len(rows) != 1:
        return None
    fhash, vuln_class, asset, source_run_id, signature = rows[0]
    sig_row = conn.execute(
        "SELECT payload FROM signals "
        "WHERE run_id = ? AND asset = ? AND signature = ? LIMIT 1",
        (source_run_id, asset, signature),
    ).fetchone()
    payload = sig_row[0] if sig_row else "{}"
    return fhash, vuln_class, asset, payload


def _extract_github_name(payload: str) -> str | None:
    """Pull the GitHub user/org name out of payload.extracted (e.g.
    'hacker0x01.github.io' → 'hacker0x01'). Returns None on parse failure."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    host = str(parsed.get("extracted", ""))
    if not host.endswith(".github.io"):
        return None
    return host[: -len(".github.io")]


def _print_verdict(
    *,
    finding_hash: str,
    asset: str,
    name: str,
    status: int,
    body: dict[str, Any],
) -> None:
    if status == 200:
        owner = body.get("login", "?")
        otype = body.get("type", "?")
        nm = body.get("name") or ""
        blog = body.get("blog") or ""
        print("VERDICT: CLAIMED")
        print(f"  github_name: {owner}  type: {otype}")
        if nm or blog:
            print(f"  github_metadata: name={nm!r} blog={blog!r}")
        print(f"  asset:       {asset}")
        print("  → likely false positive (CNAME exists but claimer owns the target)")
        print(f"  → suggested: transition {finding_hash[:8]} → resolved_na")
        print(f"    note: 'CNAME to {name}.github.io exists; "
              f"GitHub org {owner!r} is claimed by {nm or owner}, no takeover'")
    elif status == 404:
        print("VERDICT: UNCLAIMED")
        print(f"  github_name: {name}  (404 from api.github.com/users/{name})")
        print(f"  asset:       {asset}")
        print("  → possible real takeover — manual reproduction required")
        print("  → suggested: keep in queue, repro per the playbook, "
              "then transition to verified on confirmation")
    else:
        print("VERDICT: INDETERMINATE")
        print(f"  github_name: {name}")
        print(f"  asset:       {asset}")
        print(f"  api status:  {status} (expected 200 or 404)")
        print("  → retry later; if it persists, treat as needs-manual-verify")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify-takeover")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument("prefix")
    args = parser.parse_args(argv)
    paths = config.Paths.from_root(args.root)

    scope_file = paths.scope_file(args.platform, args.program)
    if not scope_file.exists():
        print(
            f"verify-takeover: program {args.platform}/{args.program!r} is not "
            f"registered (no scope.md at {scope_file})",
            file=sys.stderr,
        )
        return 1

    conn = db.open_db(paths.program_db(args.platform, args.program))
    try:
        resolved = _resolve_finding(conn, args.prefix)
    finally:
        conn.close()

    if resolved is None:
        print(
            f"verify-takeover: no finding matching prefix {args.prefix!r} in "
            f"{args.platform}/{args.program}",
            file=sys.stderr,
        )
        return 1

    finding_hash, vuln_class, asset, payload = resolved
    if "takeover" not in vuln_class:
        print(
            f"verify-takeover: {finding_hash[:8]} is not a takeover finding "
            f"(vuln_class={vuln_class!r})",
            file=sys.stderr,
        )
        return 1

    name = _extract_github_name(payload)
    if name is None:
        print(
            "verify-takeover: could not extract GitHub user/org from "
            "payload (only github-takeover supported in v1)",
            file=sys.stderr,
        )
        return 1

    status, body = _github_user_lookup(name)
    _print_verdict(
        finding_hash=finding_hash, asset=asset,
        name=name, status=status, body=body,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
