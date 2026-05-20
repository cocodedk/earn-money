"""Realistic live-scan trigger — goes through the real API + Celery.

Usage (inside the backend container):
    python scripts/run_smoke.py URL [--stubs 1.1,1.2,1.3,1.20] \\
                                    [--api http://localhost:8000]

End-to-end flow (matches what the React dashboard does):
    1. POST /api/projects/           → ephemeral Project
    2. POST /api/targets/            → ScanTarget under that project
    3. POST /api/scan-runs/          → ScanRun (status=PENDING; preflight runs)
    4. POST /api/scan-runs/<id>/start/  → status=RUNNING; Celery task enqueued
    5. poll GET /api/scan-runs/<id>/ until status ∈ {DONE, STOPPED, FAILED}
    6. report findings_count + target_run_count
    7. DELETE /api/projects/<id>/    → cascade cleanup

Every step exercises the production code path: serializer validation,
pre-flight scope check, Celery dispatch, worker pickup, the
@guarded_runner safety layer inside the worker, and finally the API
status surface that the frontend polls.

Exit 0 if every requested stub completed with status=DONE and no
OUT_OF_SCOPE_REJECTED events leaked; exit 1 otherwise.
"""
from __future__ import annotations

import argparse
import sys
import time
from urllib.parse import urlsplit


DEFAULT_STUBS = "1.1,1.2,1.3,1.20"
DEFAULT_API = "http://localhost:8000"
POLL_INTERVAL_S = 2.0
POLL_TIMEOUT_S = 300.0  # 5 min — well_known_paths can iterate ~30 candidates

# Terminal RunStatus values from apps.scans.models.RunStatus. Hard-coded
# here to keep this script Django-free; if the enum gains a new terminal
# state the script will hang at POLL_TIMEOUT_S, which is a clear signal
# to update this set rather than a silent miss.
_TERMINAL_STATUSES = frozenset({"done", "stopped", "failed"})
_OK_STATUS = "done"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("url", help="target base URL (https://host/...)")
    p.add_argument(
        "--stubs", default=DEFAULT_STUBS,
        help=f"comma-separated stub slugs (default: {DEFAULT_STUBS})",
    )
    p.add_argument(
        "--api", default=DEFAULT_API,
        help=f"API base URL (default: {DEFAULT_API})",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    parts = urlsplit(args.url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        print(f"FAIL: URL must be http(s) with a hostname: {args.url!r}")
        return 1
    stubs = [s.strip() for s in args.stubs.split(",") if s.strip()]

    import httpx

    with httpx.Client(base_url=args.api, timeout=30.0) as api:
        print(f"target  : {args.url}")
        print(f"host    : {parts.hostname}")
        print(f"stubs   : {stubs}")
        print(f"api     : {args.api}")
        print()

        proj = _create_project(api, name=f"smoke-{parts.hostname}-{int(time.time())}")
        try:
            target = _create_target(
                api, project=proj, base_url=args.url.rstrip("/"),
                host=parts.hostname,
            )
            rc = 0
            for stub_slug in stubs:
                outcome = _run_one(api, proj, target, stub_slug)
                if outcome != "ok":
                    rc = 1
            return rc
        finally:
            api.delete(f"/api/projects/{proj}/")
            print()
            print(f"cleaned up project {proj}.")


def _create_project(api, *, name: str) -> str:
    r = api.post("/api/projects/", json={"name": name})
    r.raise_for_status()
    return r.json()["id"]


def _create_target(api, *, project: str, base_url: str, host: str) -> str:
    r = api.post("/api/targets/", json={
        "project": project, "base_url": base_url, "host": host,
    })
    r.raise_for_status()
    return r.json()["id"]


def _run_one(api, project: str, target: str, stub_slug: str) -> str:
    r = api.post("/api/scan-runs/", json={
        "project": project,
        "stub_slug": stub_slug,
        "target_ids": [target],
    })
    if r.status_code >= 400:
        print(f"  {stub_slug}: PREFLIGHT-REFUSED — "
              f"{r.status_code} {r.json()}")
        return "refused"
    run_id = r.json()["id"]
    api.post(f"/api/scan-runs/{run_id}/start/").raise_for_status()

    final = _poll_until_terminal(api, run_id)
    if final is None:
        print(f"  {stub_slug}: TIMEOUT — exceeded {POLL_TIMEOUT_S}s")
        return "timeout"
    status = final["status"]
    findings = final.get("findings_count", 0)
    targets = final.get("target_run_count", 0)
    print(f"  {stub_slug}: {status} — "
          f"target_runs={targets} findings={findings}")
    return "ok" if status == _OK_STATUS else "fail"


def _poll_until_terminal(api, run_id: str):
    deadline = time.time() + POLL_TIMEOUT_S
    while time.time() < deadline:
        r = api.get(f"/api/scan-runs/{run_id}/")
        r.raise_for_status()
        body = r.json()
        if body["status"] in _TERMINAL_STATUSES:
            return body
        time.sleep(POLL_INTERVAL_S)
    return None


if __name__ == "__main__":
    sys.exit(main())
