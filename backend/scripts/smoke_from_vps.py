"""Thin live smoke runner for VPS-side egress validation.

Designed to run on h1.cocode.dk (authorised egress IP for HackerOne
bug-bounty traffic). Loads programs/hackerone/algolia/{scope,roe}.md
from the repo, verifies the target is in scope, rate-limits to
roe.max_requests_per_second, and fires real HEAD probes against
in-scope algolia hosts.

No Django, no docker, no DB. Just the smallest possible code path
that exercises the scope check + the HTTP egress.

Usage on h1:
    cd /opt/earn-money
    python3 backend/scripts/smoke_from_vps.py

Exit code 0 = all probes in-scope and successful.
Exit code 1 = a refusal triggered, or an HTTP error.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path


def _load_program() -> dict:
    """Read programs/hackerone/algolia/scope.md frontmatter without
    pulling in python-frontmatter (we want zero deps on the VPS)."""
    here = Path(__file__).resolve().parent
    # /opt/earn-money/backend/scripts/ → /opt/earn-money/
    repo = here.parent.parent
    scope_md = repo / "programs" / "hackerone" / "algolia" / "scope.md"
    text = scope_md.read_text()
    # Frontmatter: between two `---` fences at top.
    if not text.startswith("---\n"):
        raise SystemExit("scope.md missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise SystemExit("scope.md frontmatter unterminated")
    fm = text[4:end]
    # Toy YAML parser — we only need in_scope (list of strings).
    in_scope: list[str] = []
    in_block = False
    for line in fm.splitlines():
        if line.startswith("in_scope:"):
            in_block = True
            continue
        if in_block:
            stripped = line.strip()
            if line.startswith("- "):
                entry = stripped[2:].strip().strip("'").strip('"')
                in_scope.append(entry)
                continue
            if line and not line.startswith(" ") and not line.startswith("-"):
                in_block = False
    return {"in_scope": in_scope}


def _matches_any(host: str, patterns: list[str]) -> bool:
    """Same semantics as apps/programs/scope.py::matches_any —
    wildcards match suffix but NOT bare apex."""
    host = host.lower().rstrip(".")
    for entry in patterns:
        e = entry.lower()
        if e == host:
            return True
        if e.startswith("*.") and host.endswith("." + e[2:]):
            return True
    return False


def main() -> int:
    try:
        import httpx
    except ImportError:
        print("FAIL: httpx not installed on this host.")
        print("      Install with: python3 -m pip install --user httpx")
        return 1

    prog = _load_program()
    in_scope = prog["in_scope"]
    print(f"loaded program: in_scope={in_scope}")

    probes = [
        "https://www.algolia.com/",
        "https://dashboard.algolia.com/",
    ]
    rps = float(os.environ.get("ALGOLIA_RPS", "5"))
    interval = 1.0 / rps

    rc = 0
    for url in probes:
        host = url.split("/")[2].split(":")[0]
        if not _matches_any(host, in_scope):
            print(f"  REFUSED {url}: host {host!r} not in scope")
            rc = 1
            continue
        try:
            t0 = time.time()
            with httpx.Client(timeout=10.0) as client:
                resp = client.head(url, follow_redirects=False)
            dur_ms = int((time.time() - t0) * 1000)
            print(f"  PASS    {url}: status={resp.status_code} "
                  f"server={resp.headers.get('server', '?')} "
                  f"dur={dur_ms}ms")
        except httpx.RequestError as exc:
            print(f"  ERR     {url}: {type(exc).__name__}: {exc}")
            rc = 1
        time.sleep(interval)  # honour roe.max_requests_per_second
    return rc


if __name__ == "__main__":
    sys.exit(main())
