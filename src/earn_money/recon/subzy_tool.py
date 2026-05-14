"""Subprocess wrapper around the PentestPad `subzy` CLI.

Subzy fingerprints subdomain takeover candidates: for each input host it
resolves the DNS chain (CNAME → A) and matches the terminal target
against a curated list of SaaS-provider response patterns (GitHub
Pages "Site not found", Heroku "No such app", etc.). Output is a
JSON array, one entry per host.

We keep only entries with `vulnerable: true` — the other rows are
operationally interesting (HTTP_ERROR, etc.) but generate too much
noise to feed straight into `findings/_queue/`.
"""

from __future__ import annotations

import json
from typing import Any

from earn_money.recon.signals import Signal


class SubzyUnavailable(Exception):
    """Raised when the subzy binary is missing on the PATH."""


def build_command(
    targets_file: str,
    *,
    rate_limit: int,
    output_file: str = "-",
) -> list[str]:
    """Build the `subzy run` argv.

    `targets_file` is a newline-delimited file of subdomains owned by
    the runner. `rate_limit` maps onto subzy's `--concurrency` (subzy
    has no req/s throttle; concurrent goroutines is the nearest knob).
    `output_file` defaults to `-` (stdout) so the runner can capture
    JSON without an extra tmpfile.
    """
    if rate_limit <= 0:
        raise ValueError(f"rate_limit must be positive, got {rate_limit}")
    return [
        "subzy", "run",
        "--targets", targets_file,
        "--output", output_file,
        "--vuln",
        "--hide_fails",
        "--concurrency", str(rate_limit),
    ]


def parse_output(
    raw: str, *, run_id: str, observed_at: str
) -> list[Signal]:
    """Parse subzy's stdout. Tolerant of either a JSON array or JSONL.

    Returns Signals only for entries flagged `vulnerable: true`. Any
    malformed top-level or per-row issue is silently skipped — the
    audit trail lives in `recon_runs.error_summary`, not in dropped
    rows.
    """
    raw = raw.strip()
    if not raw:
        return []
    data = _try_load(raw)
    out: list[Signal] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        try:
            sig = _to_signal(entry, run_id=run_id, observed_at=observed_at)
        except (KeyError, TypeError, ValueError):
            continue
        if sig is not None:
            out.append(sig)
    return out


def _try_load(raw: str) -> list[Any]:
    """Return a list of dicts whether `raw` is a JSON array or JSONL."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return _load_jsonl(raw)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        # Some versions wrap the array in a top-level object.
        nested = parsed.get("results") or parsed.get("data")
        if isinstance(nested, list):
            return nested
    return []


def _load_jsonl(raw: str) -> list[Any]:
    out: list[Any] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _to_signal(
    entry: dict[str, Any], *, run_id: str, observed_at: str
) -> Signal | None:
    """Convert one subzy entry to a Signal. Returns None for non-vulnerable."""
    if not entry.get("vulnerable"):
        return None
    host = str(entry.get("data") or "").strip().lower()
    if not host:
        return None
    service = str(entry.get("service") or "unknown").strip().lower()
    status = str(entry.get("status") or "VULNERABLE")
    https_status = entry.get("https_status")

    target = f"https://{host}/"
    signature = f"subzy|{service}|{host}"
    payload = json.dumps(
        {
            "service": service,
            "status": status,
            "https_status": https_status,
            "severity": "high",
            "name": f"Subdomain takeover via {service}",
        },
        sort_keys=True,
    )
    return Signal(
        run_id=run_id,
        tool="subzy",
        signal_type="takeover_vulnerable",
        asset=host,
        target=target,
        signature=signature,
        payload=payload,
        observed_at=observed_at,
    )
