# Phase 3c — katana + ffuf Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the broader active-recon surface — a `katana` crawl runner (depth + duration + URL caps), a `ffuf` content-discovery runner (approved-wordlist allowlist + request caps), tool-wrapper parsers that emit normalized `Signal` rows (`endpoint_discovered` for katana, `content_match` for ffuf), and triage classify branches that turn those signals into queue candidates.

**Architecture:** Two new active runners layered on the Phase 3a primitives (`active.check_gates`, `ToolRunResult`, `KillSwitchWatchdog`, `batch.run_batches`) and the Phase 3b finding/hash/queue plumbing. Both runners mirror `nuclei_scan.run_program`: gate-check → prereq freshness against httpx (24h window) → load scoped service URLs from `http_services` → batched subprocess under the kill-switch watchdog → parse output → dual-key OOS re-filter (`sig.asset` AND `target_host(sig.target, sig.asset)` from `earn_money.recon.urls`) → write the 5 required artifact files → upsert `recon_runs`. katana is target-batchable (one subprocess per chunk, mirrors nuclei). ffuf is per-host (one subprocess per service URL because `-u <target>FUZZ` is single-target) — the runner iterates services and accumulates batch results. The triage `classify` dispatch table grows two new branches that pin the new signal types to sensible `vuln_class` / `severity_hint` / `confidence` defaults so the digest can rank them.

**Tech Stack:** Python 3.12+, sqlite3, subprocess (katana + ffuf), pytest, mypy strict, ruff. ProjectDiscovery `katana` and the Go-based `ffuf` are shelled out. No new runtime dependencies — both parsers use stdlib `json`.

**Spec reference:** [`docs/superpowers/specs/2026-05-12-phase-3-design.md`](../specs/2026-05-12-phase-3-design.md) — sections 3 (Shared Active Runner Contract + per-request scope enforcement for katana/ffuf + Shared Artifact Contract), 3.3 (katana runner), 3.4 (ffuf runner), 4 (signature composition by tool: katana = `<endpoint_path_normalized>|<sorted_parameter_names>|<method>`, ffuf = `<path_normalized>|<status_code>|<response_length_bucket>|<content_type_normalized>`), 5 (katana every 2 days at 03:15 UTC, ffuf weekly Sun 04:20 UTC), 6.3c (sub-phase scope statement).

---

## File map

**Create:**
- `src/earn_money/recon/katana_tool.py` — `build_command(targets, *, depth, duration_s, max_urls)` with caps validated against constants, `UnsafeCrawlProfile` exception, `parse_jsonl(raw, *, run_id, observed_at)` → `list[Signal]` with `signal_type="endpoint_discovered"`
- `src/earn_money/recon/ffuf_tool.py` — `build_command(target, *, wordlist_path)` with approved-wordlist allowlist, `UnsafeWordlistProfile` exception, `parse_json(raw, *, run_id, observed_at, target)` → `list[Signal]` with `signal_type="content_match"`
- `src/earn_money/runners/katana_scan.py` — runner (mirrors `nuclei_scan.run_program`)
- `src/earn_money/runners/katana_scan_cli.py` — CLI entry + real-tool wiring with watchdog
- `src/earn_money/runners/ffuf_scan.py` — runner (per-host subprocess loop)
- `src/earn_money/runners/ffuf_scan_cli.py` — CLI entry + real-tool wiring with watchdog
- `bin/katana-crawl` — sh wrapper for the runner
- `bin/ffuf-scan` — sh wrapper for the runner
- `tests/recon/test_katana_tool.py` — tool-wrapper unit tests (caps, safety flags, parser)
- `tests/recon/test_ffuf_tool.py` — tool-wrapper unit tests (wordlist allowlist, safety flags, parser)
- `tests/runners/test_katana_scan.py` — runner unit tests with injected `tool_run`
- `tests/runners/test_ffuf_scan.py` — runner unit tests with injected `tool_run`
- `tests/runners/test_katana_scan_e2e.py` — real-katana smoke against mock target (auto-skips when binary absent)
- `tests/runners/test_ffuf_scan_e2e.py` — real-ffuf smoke against mock target (auto-skips when binary absent)
- `tests/fixtures/katana_output.jsonl` — fixture for katana parser tests
- `tests/fixtures/ffuf_output.json` — fixture for ffuf parser tests
- `tests/fixtures/ffuf_wordlists/tiny.txt` — 5-line wordlist matched against the mock target's surface

**Modify:**
- `src/earn_money/triage/hashing.py` — append `signature_for_katana` and `signature_for_ffuf` composers (per spec section 4)
- `src/earn_money/triage/classify.py` — add `(katana, endpoint_discovered)` and `(ffuf, content_match)` branches
- `tests/triage/test_hashing.py` — add tests for both new signature composers
- `tests/triage/test_classify.py` — add (or extend) tests for the two new dispatch branches (note: 3b shipped `classify.py` without a dedicated test file; 3c creates `tests/triage/test_classify.py` for both 3b's existing branches and 3c's two new ones — see Task 7 for the rationale)

**Touch only when justified:** anything else. Per the project's "Surgical changes" rule, every changed line must trace back to a 3c requirement.

---

## Task 1: Signature composers for katana + ffuf

Spec section 4 fixes the signature shapes:

- **katana**: `<endpoint_path_normalized>|<sorted_parameter_names>|<method>` — parameter names sorted alphabetically, method uppercased.
- **ffuf**: `<path_normalized>|<status_code>|<response_length_bucket>|<content_type_normalized>` — `response_length_bucket` is one of `<1KB`, `1-10KB`, `10-100KB`, `100KB-1MB`, `>1MB` so jittery body sizes don't split otherwise-identical findings.

Both composers live next to `compute_hash` because they are conceptually one knot of canonicalization (the existing nuclei + httpx_anomaly composers already live there).

`endpoint_path_normalized` is the path portion of the URL after applying `_normalize_path` from `hashing.py` (rule 4 of the normalization set). We reuse the existing private helper rather than re-implementing path collapse.

`content_type_normalized` lowercases the MIME type, strips parameters (everything after `;`), and trims whitespace. `text/html; charset=UTF-8` becomes `text/html`.

**Files:**
- Modify: `src/earn_money/triage/hashing.py`
- Modify: `tests/triage/test_hashing.py`

- [ ] **Step 1: Write the failing tests for `signature_for_katana`**

```python
# tests/triage/test_hashing.py — append

def test_signature_for_katana_sorts_params_and_upcases_method() -> None:
    sig = hashing.signature_for_katana(
        url="https://api.example.com/search?b=2&a=1",
        method="get",
    )
    assert sig == "/search|a,b|GET"


def test_signature_for_katana_no_params() -> None:
    sig = hashing.signature_for_katana(
        url="https://api.example.com/docs/index",
        method="GET",
    )
    assert sig == "/docs/index||GET"


def test_signature_for_katana_normalizes_path() -> None:
    # Path collapse: //a/./b/../c → /a/c
    sig = hashing.signature_for_katana(
        url="https://api.example.com//a/./b/../c?z=9",
        method="POST",
    )
    assert sig == "/a/c|z|POST"


def test_signature_for_katana_handles_path_only_input() -> None:
    """katana sometimes emits relative refs after JS extraction; treat them
    as paths attached to the implied host."""
    sig = hashing.signature_for_katana(
        url="/admin/login?u=x",
        method="GET",
    )
    assert sig == "/admin/login|u|GET"
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/triage/test_hashing.py -v -k katana
```

Expected: `AttributeError: module 'earn_money.triage.hashing' has no attribute 'signature_for_katana'`.

- [ ] **Step 3: Implement `signature_for_katana`**

```python
# src/earn_money/triage/hashing.py — append

def signature_for_katana(*, url: str, method: str) -> str:
    """katana signature: '<endpoint_path>|<sorted_param_names>|<METHOD>'.

    Reuses `_normalize_path` and the query-string split logic so paths and
    parameter names are canonical (paths via rule 4 of the normalization
    set, parameter names alpha-sorted). The signature deliberately omits
    parameter VALUES — katana finds endpoints, not specific value combos,
    and value churn would split otherwise-identical findings.
    """
    if "://" in url:
        parts = urlsplit(url)
        path = parts.path or "/"
        query = parts.query
    else:
        # Path-only input (relative ref extracted from JS, etc.).
        path, _, query = url.partition("?")
        path = path or "/"
    path_norm = _normalize_path(path)
    param_names = sorted(_query_param_names(query))
    method_norm = (method or "GET").upper()
    return f"{path_norm}|{','.join(param_names)}|{method_norm}"


def _query_param_names(query: str) -> list[str]:
    if not query:
        return []
    names: list[str] = []
    for token in query.split("&"):
        if not token:
            continue
        name, _, _ = token.partition("=")
        if name:
            names.append(name)
    return names
```

- [ ] **Step 4: Verify GREEN for katana composer**

```bash
.venv/bin/python -m pytest tests/triage/test_hashing.py -v -k katana
```

Expected: 4 passed.

- [ ] **Step 5: Write the failing tests for `signature_for_ffuf`**

```python
# tests/triage/test_hashing.py — append

def test_signature_for_ffuf_buckets_response_length() -> None:
    sig_small = hashing.signature_for_ffuf(
        path="/admin", status_code=200,
        content_length=500, content_type="text/html",
    )
    sig_medium = hashing.signature_for_ffuf(
        path="/admin", status_code=200,
        content_length=4_500, content_type="text/html",
    )
    sig_large = hashing.signature_for_ffuf(
        path="/admin", status_code=200,
        content_length=200_000, content_type="text/html",
    )
    assert sig_small == "/admin|200|<1KB|text/html"
    assert sig_medium == "/admin|200|1-10KB|text/html"
    assert sig_large == "/admin|200|100KB-1MB|text/html"


def test_signature_for_ffuf_strips_content_type_params() -> None:
    sig = hashing.signature_for_ffuf(
        path="/api/v1", status_code=200,
        content_length=750, content_type="application/json; charset=UTF-8",
    )
    assert sig == "/api/v1|200|<1KB|application/json"


def test_signature_for_ffuf_lowercases_content_type_and_normalizes_path() -> None:
    sig = hashing.signature_for_ffuf(
        path="//Admin/./.././Admin",
        status_code=403,
        content_length=900,
        content_type="TEXT/HTML",
    )
    # path normalized to "/Admin" (case preserved), CT lowercased.
    assert sig == "/Admin|403|<1KB|text/html"


def test_signature_for_ffuf_empty_content_type_renders_as_unknown() -> None:
    sig = hashing.signature_for_ffuf(
        path="/", status_code=200, content_length=0, content_type="",
    )
    assert sig == "/|200|<1KB|unknown"


def test_signature_for_ffuf_buckets_all_five_sizes() -> None:
    """All five buckets from spec section 4."""
    for n, bucket in [
        (500, "<1KB"),
        (1024, "1-10KB"),
        (50_000, "10-100KB"),
        (500_000, "100KB-1MB"),
        (2_000_000, ">1MB"),
    ]:
        sig = hashing.signature_for_ffuf(
            path="/p", status_code=200, content_length=n,
            content_type="text/plain",
        )
        assert sig.split("|")[2] == bucket, (
            f"length {n} expected bucket {bucket}, got {sig.split('|')[2]}"
        )
```

- [ ] **Step 6: Verify RED**

```bash
.venv/bin/python -m pytest tests/triage/test_hashing.py -v -k ffuf
```

Expected: `AttributeError` for `signature_for_ffuf`.

- [ ] **Step 7: Implement `signature_for_ffuf`**

```python
# src/earn_money/triage/hashing.py — append

def signature_for_ffuf(
    *,
    path: str,
    status_code: int,
    content_length: int,
    content_type: str,
) -> str:
    """ffuf signature: '<path>|<status>|<length_bucket>|<content_type>'.

    The bucket buys stability — response bodies often jitter by a few bytes
    across runs (timestamps, request IDs, dynamic ad slots). Bucketing
    keeps the dedup key stable while still distinguishing the "tiny error
    page" case from the "real content" case.
    """
    path_norm = _normalize_path(path) if path else "/"
    bucket = _length_bucket(content_length)
    ct_norm = _normalize_content_type(content_type)
    return f"{path_norm}|{status_code}|{bucket}|{ct_norm}"


def _length_bucket(n: int) -> str:
    # Boundaries follow spec section 4 ("response_length_bucket is one of
    # <1KB, 1-10KB, 10-100KB, 100KB-1MB, >1MB"). The lower bound is
    # exclusive on the next bucket so 1024 falls into 1-10KB.
    if n < 1_024:
        return "<1KB"
    if n < 10_240:
        return "1-10KB"
    if n < 102_400:
        return "10-100KB"
    if n < 1_048_576:
        return "100KB-1MB"
    return ">1MB"


def _normalize_content_type(ct: str) -> str:
    if not ct:
        return "unknown"
    base = ct.split(";", 1)[0].strip().lower()
    return base or "unknown"
```

- [ ] **Step 8: Verify GREEN for both composers**

```bash
.venv/bin/python -m pytest tests/triage/test_hashing.py -v
```

Expected: every prior hashing test still passes plus the 4 katana + 5 ffuf new ones.

- [ ] **Step 9: Lint**

```bash
make lint
```

Expected: ruff + mypy clean.

- [ ] **Step 10: Commit**

```bash
git add src/earn_money/triage/hashing.py tests/triage/test_hashing.py
git commit -m "feat: signature composers for katana + ffuf"
```

---

## Task 2: katana tool wrapper

Thin subprocess wrapper around the `katana` CLI. Two surfaces:

1. `build_command(targets, *, depth, duration_s, max_urls)` — validates depth/duration/max_urls against constants, raises `UnsafeCrawlProfile` if any cap is exceeded.
2. `parse_jsonl(raw, *, run_id, observed_at)` — parses katana's `-jsonl` output into `list[Signal]` with `signal_type="endpoint_discovered"`.

**Approved crawl caps** (non-negotiable per CLAUDE.md "katana with depth, duration, and URL caps"):

- `MAX_DEPTH = 2` — shallow crawl only; deeper crawls produce too much noise and tend to trip WAFs.
- `MAX_DURATION_S = 600` — 10 minutes wall-clock per batch (matches the spec section 3 "Max batch duration" for katana/ffuf).
- `MAX_URLS = 5000` — per-batch hard cap on total URLs emitted.

A caller exceeding any of these raises `UnsafeCrawlProfile`. The constants are the safety boundary; an operator can extend them in this file after a manual policy review, which then becomes a code-review event (same pattern as `APPROVED_TEMPLATE_DIRS` in `nuclei_tool.py`).

**Safety flags on the command line** (per spec section 3 "Per-request scope enforcement" for katana):

- `-jsonl` — machine-readable output.
- `-silent` — suppress katana's progress chatter on stderr.
- `-no-color`.
- `-d <depth>` — crawl depth.
- `-ct <duration_s>` — total crawl-time cap (katana's `-crawl-duration`).
- `-c 10` — concurrent fetcher count cap (per-batch concurrency).
- `-rl 50` — global requests-per-second rate limit.
- `-kf robotstxt,sitemapxml` — read robots.txt + sitemap.xml hints (known-source seeding, not scope-broadening).
- `-jc` — enable JS-crawl (extract endpoints from `.js` files; in-host only because we leave `-scope-all-hosts=false` as the default).
- `-hl` — headless mode disabled (we run on a small VPS; full browser is too expensive and not needed for triage signals).
- `-iqp` — ignore query parameters when deduping katana's internal URL set; the wrapper's signature composer encodes parameter names independently.

We do **not** pass `-fs` / `-cs` (custom field/crawl scope regex) yet — the per-tool regex form is non-trivial to derive from glob patterns like `*.example.com`. Instead, the runner does a post-tool host re-filter through `scope.is_in_scope` against every emitted signal. Spec section 3 explicitly permits this: "After katana exits, the wrapper filters every emitted URL through `scope.is_in_scope` again before any signal is written; OOS URLs are silently dropped and counted in `oos_drops`." If runtime experience shows katana producing too much OOS traffic mid-crawl, a follow-up commit can derive a regex from the scope list — but that is outside Phase 3c.

**JSONL shape from katana** (verified against `katana -version` v1.0.5 output on the VPS):

```json
{"timestamp":"2026-05-12T03:15:00Z","request":{"method":"GET","endpoint":"https://api.example.com/search","tag":"body","source":"https://api.example.com/"}}
{"timestamp":"2026-05-12T03:15:01Z","request":{"method":"POST","endpoint":"https://api.example.com/api/v1/login","tag":"form","source":"https://api.example.com/login"}}
```

Each line has a `request` object with `method` and `endpoint`. Older katana versions emit a flat `{"timestamp":"...","url":"..."}`; the parser handles both shapes defensively.

**Files:**
- Create: `src/earn_money/recon/katana_tool.py`
- Create: `tests/recon/test_katana_tool.py`
- Create: `tests/fixtures/katana_output.jsonl`

- [ ] **Step 1: Write the katana fixture**

```jsonl
# tests/fixtures/katana_output.jsonl
{"timestamp":"2026-05-12T03:15:00Z","request":{"method":"GET","endpoint":"https://api.example.com/search?q=foo","tag":"body","source":"https://api.example.com/"}}
{"timestamp":"2026-05-12T03:15:01Z","request":{"method":"POST","endpoint":"https://api.example.com/api/v1/login","tag":"form","source":"https://api.example.com/login"}}
{"timestamp":"2026-05-12T03:15:02Z","request":{"method":"GET","endpoint":"https://api.example.com/admin/dashboard","tag":"href","source":"https://api.example.com/"}}
```

(The trailing comment line is for the plan — the file itself is just the three JSONL rows; do not write the `# tests/fixtures/...` comment into the actual fixture.)

- [ ] **Step 2: Write the failing test**

```python
# tests/recon/test_katana_tool.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from earn_money.recon import katana_tool


def test_caps_constants_locked() -> None:
    """The crawl caps are the safety boundary — locking them prevents an
    accidental edit from broadening the blast radius."""
    assert katana_tool.MAX_DEPTH == 2
    assert katana_tool.MAX_DURATION_S == 600
    assert katana_tool.MAX_URLS == 5000


def test_build_command_includes_safety_flags() -> None:
    cmd = katana_tool.build_command(
        ["https://api.example.com/"],
        depth=2, duration_s=600, max_urls=5000,
    )
    assert "-jsonl" in cmd
    assert "-silent" in cmd
    assert "-no-color" in cmd
    assert "-d" in cmd and cmd[cmd.index("-d") + 1] == "2"
    assert "-ct" in cmd and cmd[cmd.index("-ct") + 1] == "600"
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "10"
    assert "-rl" in cmd and cmd[cmd.index("-rl") + 1] == "50"
    assert "-kf" in cmd and cmd[cmd.index("-kf") + 1] == "robotstxt,sitemapxml"
    assert "-jc" in cmd
    assert "-hl" in cmd
    assert "-iqp" in cmd


def test_build_command_passes_targets_via_list() -> None:
    cmd = katana_tool.build_command(
        ["https://api.example.com/", "https://www.example.com/"],
        depth=1, duration_s=120, max_urls=500,
    )
    # katana takes -u with comma-separated URLs, same shape as nuclei.
    assert "-u" in cmd
    u_index = cmd.index("-u")
    assert cmd[u_index + 1] == "https://api.example.com/,https://www.example.com/"


def test_build_command_rejects_excessive_depth() -> None:
    with pytest.raises(katana_tool.UnsafeCrawlProfile, match="depth"):
        katana_tool.build_command(
            ["https://api.example.com/"],
            depth=5, duration_s=600, max_urls=5000,
        )


def test_build_command_rejects_excessive_duration() -> None:
    with pytest.raises(katana_tool.UnsafeCrawlProfile, match="duration"):
        katana_tool.build_command(
            ["https://api.example.com/"],
            depth=2, duration_s=3600, max_urls=5000,
        )


def test_build_command_rejects_excessive_max_urls() -> None:
    with pytest.raises(katana_tool.UnsafeCrawlProfile, match="max_urls"):
        katana_tool.build_command(
            ["https://api.example.com/"],
            depth=2, duration_s=600, max_urls=100_000,
        )


def test_build_command_empty_targets_raises() -> None:
    with pytest.raises(ValueError):
        katana_tool.build_command(
            [], depth=2, duration_s=600, max_urls=5000,
        )


def test_parse_jsonl_returns_signals(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "katana_output.jsonl").read_text(encoding="utf-8")
    sigs = katana_tool.parse_jsonl(
        raw, run_id="r1", observed_at="2026-05-12T03:30:00Z"
    )
    assert len(sigs) == 3
    s = next(x for x in sigs if "/search" in x.signature)
    assert s.signal_type == "endpoint_discovered"
    assert s.asset == "api.example.com"
    assert s.target == "https://api.example.com/search?q=foo"
    assert s.signature == "/search|q|GET"


def test_parse_jsonl_payload_carries_method_and_source(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "katana_output.jsonl").read_text(encoding="utf-8")
    sigs = katana_tool.parse_jsonl(raw, run_id="r1", observed_at="t")
    login = next(x for x in sigs if "/api/v1/login" in x.signature)
    payload = json.loads(login.payload)
    assert payload["method"] == "POST"
    assert payload["source"] == "https://api.example.com/login"
    assert payload["endpoint"] == "https://api.example.com/api/v1/login"


def test_parse_jsonl_skips_malformed_lines(fixtures_dir: Path) -> None:
    raw = "not json\n" + (fixtures_dir / "katana_output.jsonl").read_text(encoding="utf-8")
    sigs = katana_tool.parse_jsonl(raw, run_id="r1", observed_at="t")
    assert len(sigs) == 3


def test_parse_jsonl_handles_flat_url_shape() -> None:
    """Older katana versions emit {"timestamp": "...", "url": "..."} instead
    of the nested request object. Parser tolerates both."""
    raw = '{"timestamp":"t","url":"https://api.example.com/legacy"}\n'
    sigs = katana_tool.parse_jsonl(raw, run_id="r1", observed_at="t")
    assert len(sigs) == 1
    assert sigs[0].target == "https://api.example.com/legacy"
    assert sigs[0].signature == "/legacy||GET"
```

- [ ] **Step 3: Verify RED**

```bash
.venv/bin/python -m pytest tests/recon/test_katana_tool.py -v
```

Expected: `ModuleNotFoundError: No module named 'earn_money.recon.katana_tool'`.

- [ ] **Step 4: Implement the wrapper**

```python
# src/earn_money/recon/katana_tool.py
"""Subprocess wrapper around the ProjectDiscovery `katana` CLI.

This wrapper is the safety boundary for katana. It refuses to build a
command that exceeds the crawl caps (MAX_DEPTH / MAX_DURATION_S /
MAX_URLS) and forces the safety flags on every invocation
(`-d`, `-ct`, `-rl`, `-c`, `-jsonl`, `-silent`, `-no-color`, plus
known-source seeding via `-kf robotstxt,sitemapxml`).

The post-tool scope re-filter lives in the runner, not here — the spec
section 3 contract is that the wrapper drops any URL whose host resolves
out-of-scope after the crawl exits, even if katana itself emitted it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from earn_money.recon.signals import Signal
from earn_money.triage import hashing

# Crawl caps — see plan section "Approved crawl caps" for rationale.
MAX_DEPTH = 2
MAX_DURATION_S = 600
MAX_URLS = 5000


class UnsafeCrawlProfile(Exception):
    """Raised when build_command is asked to exceed an approved cap."""


def build_command(
    targets: Sequence[str],
    *,
    depth: int,
    duration_s: int,
    max_urls: int,
) -> list[str]:
    if not targets:
        raise ValueError("build_command requires at least one target")
    if depth > MAX_DEPTH:
        raise UnsafeCrawlProfile(
            f"refusing to crawl at depth={depth}; "
            f"max approved depth is {MAX_DEPTH}"
        )
    if duration_s > MAX_DURATION_S:
        raise UnsafeCrawlProfile(
            f"refusing to crawl for duration_s={duration_s}; "
            f"max approved duration_s is {MAX_DURATION_S}"
        )
    if max_urls > MAX_URLS:
        raise UnsafeCrawlProfile(
            f"refusing to crawl with max_urls={max_urls}; "
            f"max approved max_urls is {MAX_URLS}"
        )
    return [
        "katana",
        "-u", ",".join(targets),
        "-d", str(depth),
        "-ct", str(duration_s),
        "-c", "10",
        "-rl", "50",
        "-kf", "robotstxt,sitemapxml",
        "-jc",
        "-hl",
        "-iqp",
        "-jsonl",
        "-silent",
        "-no-color",
    ]


def parse_jsonl(
    raw: str, *, run_id: str, observed_at: str
) -> list[Signal]:
    """Parse katana's JSONL output into Signal rows.

    Each emitted URL becomes one Signal with signal_type="endpoint_discovered".
    Two shapes are supported: the modern `{"request":{...}}` and the legacy
    flat `{"url":"..."}` form.
    """
    out: list[Signal] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            out.append(_to_signal(data, run_id=run_id, observed_at=observed_at))
        except (KeyError, ValueError):
            continue
    return out


def _to_signal(
    data: dict[str, Any], *, run_id: str, observed_at: str
) -> Signal:
    req = data.get("request") or {}
    endpoint = str(req.get("endpoint") or data.get("url") or "")
    if not endpoint:
        raise ValueError("katana row has no endpoint/url")
    method = str(req.get("method") or "GET").upper()
    source = str(req.get("source") or "")
    tag = str(req.get("tag") or "")

    asset = hashing.normalize_asset(endpoint)
    target = hashing.normalize_target(endpoint)
    signature = hashing.signature_for_katana(url=endpoint, method=method)
    payload = json.dumps({
        "endpoint": endpoint,
        "method": method,
        "source": source,
        "tag": tag,
    }, sort_keys=True)
    return Signal(
        run_id=run_id, tool="katana", signal_type="endpoint_discovered",
        asset=asset, target=target, signature=signature,
        payload=payload, observed_at=observed_at,
    )
```

- [ ] **Step 5: Verify GREEN**

```bash
.venv/bin/python -m pytest tests/recon/test_katana_tool.py -v
make lint
```

Expected: 11 passed; lint clean.

- [ ] **Step 6: Commit**

```bash
git add src/earn_money/recon/katana_tool.py tests/recon/test_katana_tool.py \
        tests/fixtures/katana_output.jsonl
git commit -m "feat: katana tool wrapper with crawl caps + safety flags"
```

---

## Task 3: katana runner

Mirrors `nuclei_scan.run_program` exactly. Differences from nuclei:

1. **Signal type**: `endpoint_discovered`.
2. **Tool name in artifacts**: `katana`. Artifact dir: `recon/outputs/<platform>/<slug>/katana/<YYYY-MM-DD>/<run_id>/`.
3. **Tool build invocation**: passes `MAX_DEPTH`, `MAX_DURATION_S`, `MAX_URLS` from `katana_tool` constants.
4. **Per-batch duration**: 600s (10 minutes — see spec section 3 "Max batch duration").
5. **Manifest** records the crawl caps actually used.

Everything else — gate check, prereq freshness check on httpx (24h window), dual-key OOS re-filter, 5 required artifacts, watchdog reason capture — is identical to `nuclei_scan`.

The runner stays under the 200-line cap by extracting `_build_real_tool` + `main()` to `katana_scan_cli.py`, exactly like `nuclei_scan_cli.py`.

**Files:**
- Create: `src/earn_money/runners/katana_scan.py`
- Create: `src/earn_money/runners/katana_scan_cli.py`
- Create: `tests/runners/test_katana_scan.py`

- [ ] **Step 1: Write the failing test (gate refusal + prereq missing)**

```python
# tests/runners/test_katana_scan.py
"""Tests for the katana-crawl active-recon runner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from earn_money import config, db, flags, policy, scope
from earn_money.recon import services, signals
from earn_money.runners import active, katana_scan


def _seed_scope(
    paths: config.Paths,
    *,
    policy_value: scope.Policy = "rate-limited-OK",
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope or ["*.example.com"],
        out_of_scope=out_of_scope or [],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _seed_httpx_run_and_services(
    paths: config.Paths, *, services_to_insert: list[services.HttpService]
) -> None:
    from earn_money.recon import runs
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="httpx-r1", platform="hackerone", slug="example",
            tool="httpx", started_at="2026-05-12T01:00:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-r1", finished_at="2026-05-12T01:05:00Z",
            status="success", output_count=len(services_to_insert),
            signal_count=0, source_failures=0, oos_drops=0,
        )
        for svc in services_to_insert:
            services.upsert_service(conn, svc)
    finally:
        conn.close()


def test_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths)
    with pytest.raises(flags.ReconDisabled):
        katana_scan.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: active.ToolRunResult(outputs=()),
        )


def test_refuses_manual_only(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, policy_value="manual-only")
    with pytest.raises(policy.PolicyViolation):
        katana_scan.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: active.ToolRunResult(outputs=()),
        )


def test_writes_prereq_missing_signal_when_no_recent_httpx(
    tmp_repo: Path,
) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)

    result = katana_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _targets: active.ToolRunResult(outputs=()),
    )
    assert result.targets_scanned == 0
    assert result.signals_emitted == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT signal_type FROM signals WHERE tool = 'katana'"
    ).fetchall()
    run_status = conn.execute(
        "SELECT status, error_summary FROM recon_runs WHERE tool = 'katana'"
    ).fetchone()
    conn.close()
    assert rows == [("prereq_missing",)]
    assert run_status[0] == "skipped"
    assert "no recent httpx run" in run_status[1]
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/runners/test_katana_scan.py -v
```

Expected: `ModuleNotFoundError: No module named 'earn_money.runners.katana_scan'`.

- [ ] **Step 3: Implement the runner**

```python
# src/earn_money/runners/katana_scan.py
"""Crawl-based endpoint-discovery runner.

Mirrors nuclei_scan but emits `endpoint_discovered` signals from katana's
JSONL output. Per spec section 3, every emitted URL is re-checked
against the program's scope (`oos_drops` counts the rejects) on both
``sig.asset`` AND ``target_host(sig.target, sig.asset)`` (imported from
``earn_money.recon.urls``).

Per spec section 7, the runner refuses to scan if there is no recent
successful httpx run (prereq freshness check, 24h window).  The refusal
is graceful: a `prereq_missing` Signal is written and the recon_runs row
is marked `status='skipped'`.

CLI entry-point and real-tool wiring live in katana_scan_cli.py so this
file stays under the 200-line cap.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from earn_money import config, db, scope
from earn_money.recon import katana_tool, runs, signals
from earn_money.recon.signals import Signal
from earn_money.recon.urls import target_host
from earn_money.runners import active

ToolRun = Callable[[list[str]], active.ToolRunResult]

_PREREQ_FRESHNESS_HOURS = 24


def _load_in_scope_service_urls(
    conn: sqlite3.Connection, s: scope.Scope
) -> list[str]:
    cursor = conn.execute(
        "SELECT url, subdomain FROM http_services "
        "WHERE in_scope_at_observation = 1 ORDER BY subdomain, scheme, port"
    )
    return [
        url for url, subdomain in cursor
        if scope.is_in_scope(subdomain, s.in_scope, s.out_of_scope)
    ]


def _recent_httpx_success(
    conn: sqlite3.Connection, *, platform: str, slug: str, now: datetime,
) -> bool:
    cutoff = (now - timedelta(hours=_PREREQ_FRESHNESS_HOURS)).isoformat(
        timespec="seconds"
    )
    row = conn.execute(
        "SELECT 1 FROM recon_runs WHERE platform = ? AND slug = ? "
        "AND tool = 'httpx' AND status IN ('success', 'partial') "
        "AND output_count > 0 "
        "AND finished_at IS NOT NULL AND finished_at >= ? LIMIT 1",
        (platform, slug, cutoff),
    ).fetchone()
    return row is not None


def _write_manifest(artifact_dir: Path, payload: dict[str, Any]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def _write_signals_jsonl(artifact_dir: Path, sigs: list[Signal]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with (artifact_dir / "signals.jsonl").open("w", encoding="utf-8") as fh:
        for s in sigs:
            fh.write(json.dumps({
                "tool": s.tool, "signal_type": s.signal_type,
                "asset": s.asset, "target": s.target,
                "signature": s.signature, "payload": s.payload,
                "observed_at": s.observed_at,
            }) + "\n")


def _write_required_artifacts(
    artifact_dir: Path,
    *,
    targets: list[str],
    raw_stdout: str,
    raw_stderr: str,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "input.txt").write_text(
        "\n".join(targets) + ("\n" if targets else ""), encoding="utf-8"
    )
    (artifact_dir / "raw.jsonl").write_text(raw_stdout, encoding="utf-8")
    (artifact_dir / "stderr.txt").write_text(raw_stderr, encoding="utf-8")


def run_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    tool_run: ToolRun,
    run_id: str | None = None,
) -> active.ActiveRunResult:
    """Gate-check → prereq freshness → load services → crawl → filter → record."""
    s = active.check_gates(paths, platform, slug, mode="active")

    run_id = run_id or uuid.uuid4().hex
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat(timespec="seconds")
    artifact_dir = paths.root / (
        f"recon/outputs/{platform}/{slug}/katana/{now[:10]}/{run_id}"
    )

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        if not _recent_httpx_success(conn, platform=platform, slug=slug, now=now_dt):
            return _record_prereq_missing(
                conn, platform, slug, run_id, now, artifact_dir,
            )

        targets = _load_in_scope_service_urls(conn, s)
        runs.start_run(
            conn, run_id=run_id, platform=platform, slug=slug, tool="katana",
            started_at=now, artifact_dir=str(artifact_dir), input_count=len(targets),
        )

        try:
            tool_result = (
                tool_run(targets) if targets
                else active.ToolRunResult(outputs=())
            )
        except Exception as exc:
            finished = datetime.now(UTC).isoformat(timespec="seconds")
            runs.finish_run(
                conn, run_id=run_id, finished_at=finished, status="failed",
                output_count=0, signal_count=0, source_failures=1, oos_drops=0,
                error_summary=f"{type(exc).__name__}: {exc}",
            )
            raise

        raw_signals: list[Signal] = list(tool_result.outputs)
        in_scope_sigs = [
            sig for sig in raw_signals
            if scope.is_in_scope(sig.asset, s.in_scope, s.out_of_scope)
            and scope.is_in_scope(
                target_host(sig.target, sig.asset), s.in_scope, s.out_of_scope,
            )
        ]
        oos_drops = len(raw_signals) - len(in_scope_sigs)

        if in_scope_sigs:
            signals.insert_signals(conn, in_scope_sigs)
        _write_signals_jsonl(artifact_dir, in_scope_sigs)
        _write_required_artifacts(
            artifact_dir,
            targets=targets,
            raw_stdout=tool_result.raw_stdout,
            raw_stderr=tool_result.raw_stderr,
        )
        _write_manifest(artifact_dir, {
            "run_id": run_id, "tool": "katana",
            "platform": platform, "slug": slug,
            "started_at": now, "input_count": len(targets),
            "signal_count": len(in_scope_sigs), "oos_drops": oos_drops,
            "crawl_caps": {
                "max_depth": katana_tool.MAX_DEPTH,
                "max_duration_s": katana_tool.MAX_DURATION_S,
                "max_urls": katana_tool.MAX_URLS,
            },
        })

        terminated_reason: str | None = (
            tool_result.terminated_reason
            or ("kill_switch" if tool_result.aborted else None)
            or ("timeout" if tool_result.timed_out else None)
        )
        run_status = "partial" if terminated_reason else "success"

        finished = datetime.now(UTC).isoformat(timespec="seconds")
        runs.finish_run(
            conn, run_id=run_id, finished_at=finished, status=run_status,
            output_count=len(in_scope_sigs),
            signal_count=len(in_scope_sigs),
            source_failures=tool_result.source_failures, oos_drops=oos_drops,
            terminated_reason=terminated_reason,
        )
        return active.ActiveRunResult(
            run_id=run_id,
            targets_considered=len(targets),
            targets_scanned=len(targets),
            artifacts_written=1,
            signals_emitted=len(in_scope_sigs),
            source_failures=tool_result.source_failures,
            oos_drops=oos_drops,
        )
    finally:
        conn.close()


def _record_prereq_missing(
    conn: sqlite3.Connection,
    platform: str,
    slug: str,
    run_id: str,
    now: str,
    artifact_dir: Path,
) -> active.ActiveRunResult:
    runs.start_run(
        conn, run_id=run_id, platform=platform, slug=slug, tool="katana",
        started_at=now, artifact_dir=str(artifact_dir), input_count=0,
    )
    prereq_sig = Signal(
        run_id=run_id, tool="katana", signal_type="prereq_missing",
        asset="", target="",
        signature=f"prereq|httpx|<{_PREREQ_FRESHNESS_HOURS}h",
        payload=json.dumps({
            "required_tool": "httpx",
            "max_age_hours": _PREREQ_FRESHNESS_HOURS,
        }),
        observed_at=now,
    )
    signals.insert_signals(conn, [prereq_sig])
    _write_signals_jsonl(artifact_dir, [prereq_sig])
    _write_required_artifacts(artifact_dir, targets=[], raw_stdout="", raw_stderr="")
    _write_manifest(artifact_dir, {
        "run_id": run_id, "tool": "katana",
        "platform": platform, "slug": slug, "started_at": now,
        "status": "skipped", "reason": "no recent httpx run",
    })
    finished = datetime.now(UTC).isoformat(timespec="seconds")
    runs.finish_run(
        conn, run_id=run_id, finished_at=finished, status="skipped",
        output_count=0, signal_count=1, source_failures=0, oos_drops=0,
        error_summary="no recent httpx run within prereq freshness window",
    )
    return active.ActiveRunResult(
        run_id=run_id, targets_considered=0, targets_scanned=0,
        artifacts_written=1, signals_emitted=1, source_failures=0, oos_drops=0,
    )
```

The file is at ~190 lines, just under the 200-line cap. The CLI module sits in `katana_scan_cli.py`.

- [ ] **Step 4: Implement `katana_scan_cli.py`**

```python
# src/earn_money/runners/katana_scan_cli.py
"""CLI entry-point and real-tool wiring for katana-crawl.

Kept in a sibling module so `katana_scan.py` stays under the 200-line cap.
"""

from __future__ import annotations

import argparse
import sys
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from earn_money import config, flags, policy
from earn_money.recon import katana_tool
from earn_money.runners import active, katana_scan


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str
) -> Callable[[list[str]], active.ToolRunResult]:
    """Wire the kill-switch watchdog + batch runner + katana tool parser."""
    from earn_money.runners import batch, watchdog

    def real_tool(targets: list[str]) -> active.ToolRunResult:
        abort = threading.Event()
        abort_reason: list[str | None] = [None]

        def on_state_change(reason: str) -> None:
            abort_reason[0] = reason
            abort.set()

        wd = watchdog.KillSwitchWatchdog(
            paths, platform=platform, slug=slug,
            on_state_change=on_state_change,
            poll_interval_s=5.0,
        )
        wd.start()
        try:
            batches_result = batch.run_batches(
                targets,
                command_factory=lambda chunk: katana_tool.build_command(
                    chunk,
                    depth=katana_tool.MAX_DEPTH,
                    duration_s=katana_tool.MAX_DURATION_S,
                    max_urls=katana_tool.MAX_URLS,
                ),
                max_batch_size=50,
                max_batch_duration_s=float(katana_tool.MAX_DURATION_S),
                abort=abort,
            )
        finally:
            wd.stop()

        raw_stdout = "\n".join(
            line for b in batches_result.batches for line in b.lines
        )
        raw_stderr = "\n".join(
            b.stderr for b in batches_result.batches if b.stderr
        )
        now = datetime.now(UTC).isoformat(timespec="seconds")
        source_failures = sum(
            1 for b in batches_result.batches
            if b.timed_out or b.return_code not in (0, None)
        )
        timed_out = any(b.timed_out for b in batches_result.batches)
        parsed = katana_tool.parse_jsonl(raw_stdout, run_id=run_id, observed_at=now)
        return active.ToolRunResult(
            outputs=tuple(parsed),
            aborted=batches_result.aborted,
            terminated_reason=abort_reason[0],
            source_failures=source_failures,
            timed_out=timed_out,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
        )

    return real_tool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="katana-crawl")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    run_id = uuid.uuid4().hex
    real_tool = _build_real_tool(
        paths, platform=args.platform, slug=args.program, run_id=run_id
    )

    try:
        result = katana_scan.run_program(
            paths, args.platform, args.program,
            tool_run=real_tool, run_id=run_id,
        )
    except flags.ReconDisabled as e:
        print(f"katana-crawl: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"katana-crawl: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"katana-crawl: {e}", file=sys.stderr)
        return 4
    except katana_tool.UnsafeCrawlProfile as e:
        print(f"katana-crawl: {e}", file=sys.stderr)
        return 5
    except Exception as e:
        print(
            f"katana-crawl: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    print(
        f"katana-crawl: scanned={result.targets_scanned} "
        f"signals={result.signals_emitted} "
        f"oos_drops={result.oos_drops} "
        f"source_failures={result.source_failures}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Verify the gate + prereq tests GREEN**

```bash
.venv/bin/python -m pytest tests/runners/test_katana_scan.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Write the happy-path test (writes signals + all 5 artifacts)**

```python
# tests/runners/test_katana_scan.py — append

def test_writes_signals_for_in_scope_services(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])

    _seed_httpx_run_and_services(
        paths, services_to_insert=[
            services.HttpService(
                subdomain="api.example.com", scheme="https", port=443,
                url="https://api.example.com/", status_code=200, title=None,
                server=None, technologies=(), redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
            ),
        ],
    )

    captured_targets: list[list[str]] = []

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        captured_targets.append(list(targets))
        return active.ToolRunResult(outputs=(
            signals.Signal(
                run_id="r", tool="katana", signal_type="endpoint_discovered",
                asset="api.example.com",
                target="https://api.example.com/search?q=foo",
                signature="/search|q|GET",
                payload='{"method":"GET","endpoint":"https://api.example.com/search?q=foo"}',
                observed_at="2026-05-12T03:16:00Z",
            ),
        ))

    result = katana_scan.run_program(
        paths, "hackerone", "example", tool_run=fake_tool,
        run_id="katana-r1",
    )
    assert result.signals_emitted == 1
    assert result.oos_drops == 0
    assert captured_targets == [["https://api.example.com/"]]

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    sigs = conn.execute(
        "SELECT signal_type, asset, signature FROM signals "
        "WHERE tool = 'katana'"
    ).fetchall()
    runs_rows = conn.execute(
        "SELECT status FROM recon_runs WHERE tool = 'katana'"
    ).fetchall()
    conn.close()
    assert sigs == [("endpoint_discovered", "api.example.com", "/search|q|GET")]
    assert runs_rows == [("success",)]

    # All 5 required artifact files exist.
    katana_out = (
        paths.root / "recon" / "outputs" / "hackerone" / "example" / "katana"
    )
    assert len(list(katana_out.rglob("manifest.json"))) == 1
    assert len(list(katana_out.rglob("signals.jsonl"))) == 1
    assert len(list(katana_out.rglob("input.txt"))) == 1
    assert len(list(katana_out.rglob("raw.jsonl"))) == 1
    assert len(list(katana_out.rglob("stderr.txt"))) == 1
```

Run + verify GREEN.

- [ ] **Step 7: Write the OOS drop tests (asset + target dual-key)**

```python
# tests/runners/test_katana_scan.py — append

def test_drops_oos_signals_from_tool_output(tmp_repo: Path) -> None:
    """A signal whose sig.asset resolves OOS must be dropped."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def leaky_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(
            signals.Signal(
                run_id="r", tool="katana", signal_type="endpoint_discovered",
                asset="api.example.com", target="https://api.example.com/ok",
                signature="/ok||GET", payload="{}", observed_at="t",
            ),
            signals.Signal(
                run_id="r", tool="katana", signal_type="endpoint_discovered",
                asset="evil.example.com", target="https://evil.example.com/x",
                signature="/x||GET", payload="{}", observed_at="t",
            ),
        ))

    result = katana_scan.run_program(
        paths, "hackerone", "example", tool_run=leaky_tool,
    )
    assert result.signals_emitted == 1
    assert result.oos_drops == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT asset FROM signals WHERE tool = 'katana'"
    ).fetchall()
    conn.close()
    assert rows == [("api.example.com",)]


def test_drops_signals_with_oos_target_even_if_asset_in_scope(
    tmp_repo: Path,
) -> None:
    """Dual-key filter: a signal whose asset is in-scope but target URL
    points to an OOS host (katana followed a same-host link to a CNAME
    that's marked OOS) is dropped and counted as oos_drops."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def leaky_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(
            signals.Signal(
                run_id="r", tool="katana", signal_type="endpoint_discovered",
                asset="api.example.com",  # in-scope asset
                target="https://evil.example.com/leaked",  # OOS target!
                signature="/leaked||GET", payload="{}", observed_at="t",
            ),
        ))

    result = katana_scan.run_program(
        paths, "hackerone", "example", tool_run=leaky_tool,
    )
    assert result.oos_drops == 1
    assert result.signals_emitted == 0
```

Run + verify GREEN.

- [ ] **Step 8: Write the prereq-still-writes-artifacts test**

```python
# tests/runners/test_katana_scan.py — append

def test_prereq_missing_still_writes_required_artifacts(tmp_repo: Path) -> None:
    """_record_prereq_missing must write all 5 required artifacts so the
    artifact contract holds even for skipped runs."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)

    result = katana_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _targets: active.ToolRunResult(outputs=()),
    )
    assert result.signals_emitted == 1  # the prereq_missing signal

    katana_out = paths.root / "recon" / "outputs" / "hackerone" / "example" / "katana"
    for name in ("manifest.json", "signals.jsonl", "input.txt", "raw.jsonl", "stderr.txt"):
        files = list(katana_out.rglob(name))
        assert len(files) == 1, f"missing required artifact: {name}"
```

Run + verify GREEN.

- [ ] **Step 9: Write the watchdog terminated_reason capture test**

```python
# tests/runners/test_katana_scan.py — append

def test_records_terminated_reason_from_tool_result(tmp_repo: Path) -> None:
    """When the watchdog signals 'kill_switch' mid-batch, the runner must
    record the reason in recon_runs.terminated_reason and mark status='partial'."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def aborted_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(
            outputs=(),
            aborted=True,
            terminated_reason="kill_switch",
        )

    result = katana_scan.run_program(
        paths, "hackerone", "example", tool_run=aborted_tool,
    )
    assert result.signals_emitted == 0

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT status, terminated_reason FROM recon_runs WHERE tool = 'katana'"
    ).fetchone()
    conn.close()
    assert row == ("partial", "kill_switch")
```

Run + verify GREEN.

- [ ] **Step 10: Lint**

```bash
make lint
```

- [ ] **Step 11: Commit**

```bash
git add src/earn_money/runners/katana_scan.py \
        src/earn_money/runners/katana_scan_cli.py \
        tests/runners/test_katana_scan.py
git commit -m "feat: katana-crawl runner with prereq freshness + OOS re-filter"
```

---

## Task 4: `bin/katana-crawl` CLI

Same shape as `bin/nuclei-scan`. Sh script, sources `.env`, invokes the runner via the package's CLI module.

**Files:**
- Create: `bin/katana-crawl`

- [ ] **Step 1: Write the script**

```sh
#!/bin/sh
# Thin wrapper around the katana-crawl runner.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/.env"
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "katana-crawl: .venv not found at $ROOT/.venv — run 'make install-dev' first" >&2
  exit 1
fi

exec "$ROOT/.venv/bin/python" -m earn_money.runners.katana_scan_cli --root "$ROOT" "$@"
```

- [ ] **Step 2: Make executable and verify**

```bash
chmod +x bin/katana-crawl
bin/katana-crawl --help
```

Expected: argparse usage line for `katana-crawl`.

- [ ] **Step 3: Commit**

```bash
git add bin/katana-crawl
git commit -m "feat: bin/katana-crawl CLI wrapper"
```

---

## Task 5: ffuf tool wrapper

Thin subprocess wrapper around the `ffuf` CLI. Two surfaces:

1. `build_command(target, *, wordlist_path)` — validates `wordlist_path.name` is in `APPROVED_WORDLISTS`. Raises `UnsafeWordlistProfile` otherwise.
2. `parse_json(raw, *, run_id, observed_at, target)` — parses ffuf's `-of json` output (a **single JSON object** with a `results` array, not JSONL) into `list[Signal]` with `signal_type="content_match"`.

**Approved wordlist allowlist** (non-negotiable per CLAUDE.md "approved wordlists"):

```python
APPROVED_WORDLISTS: frozenset[str] = frozenset({
    "common.txt",
    "raft-medium-directories.txt",
})
```

These are basenames (the last path component). The operator is expected to keep the actual files in a configurable wordlists root — the runner reads `WORDLISTS_DIR` from `os.environ` and joins with the basename. `build_command` only inspects the basename, never the directory; this keeps the wrapper deterministic and the safety check trivial to audit.

Why basename-only and not full-path matching: full-path matching is fragile across deployment hosts (the operator laptop's wordlists may live at `/opt/seclists/...`; the VPS's at `/usr/share/seclists/...`). Basename + directory env var is the clean separation.

**Safety flags on the command line** (per spec section 3 "Per-request scope enforcement" for ffuf):

- `-of json` — single JSON output (ffuf does not have a true JSONL mode; `-of json` writes one large JSON object with `results` array, which we parse below).
- `-o <output_file>` — required by ffuf when `-of json` is set; we pipe to a temp file rather than stdout because some ffuf versions write progress to stdout when `-o` is absent.
- `-c` — colour off (ffuf's `-c` is "enable colors"; we explicitly do NOT pass it — leaving colour off is the default). Note: do not confuse with nuclei's `-c <int>` concurrency cap. ffuf's concurrency flag is `-t`.
- `-t 10` — 10 concurrent threads (per-host concurrency cap).
- `-rate 50` — 50 requests/second global rate limit.
- `-timeout 10` — 10-second timeout per request.
- `-mc 200,204,301,302,307,401,403` — match status codes (everything else is filtered out).
- `-fc 404` — filter out 404 explicitly (some servers return 200-with-error-page; the post-match logic re-buckets, but 404 we drop pre-emptively).
- `-ac` — auto-calibrate: ffuf detects baseline-noise responses (wildcard 200s, soft-404s) and filters them. Per spec section 3.4 "The runner must auto-calibrate where possible and cap request volume per root."
- `-recursion -recursion-depth 1` — recurse one level into discovered directories (matches the "shallow" intent of Phase 3c).
- `-w <wordlist_path>:FUZZ` — wordlist binding to the `FUZZ` keyword. We **do not** pass `-r` (follow-redirects) per spec section 3.

ffuf's per-request follow-redirects default is **off** in current versions (verified `ffuf -h | grep -F follow`); the wrapper explicitly does not pass `-r` so the default holds. We do not pass `-fr` (filter regex) either — the dual-key OOS re-filter in the runner is the authoritative scope enforcement for ffuf output, mirroring katana.

**JSON output shape from ffuf** (`-of json`):

```json
{
  "commandline": "ffuf ...",
  "time": "2026-05-12T04:20:00Z",
  "results": [
    {
      "input": {"FUZZ": "admin"},
      "position": 0,
      "status": 200,
      "length": 1234,
      "words": 56,
      "lines": 12,
      "content-type": "text/html; charset=utf-8",
      "redirectlocation": "",
      "duration": 12345678,
      "resultfile": "",
      "url": "https://api.example.com/admin",
      "host": "api.example.com"
    }
  ]
}
```

The parser walks `results[]` and turns each entry into one Signal.

**Files:**
- Create: `src/earn_money/recon/ffuf_tool.py`
- Create: `tests/recon/test_ffuf_tool.py`
- Create: `tests/fixtures/ffuf_output.json`

- [ ] **Step 1: Write the ffuf JSON fixture**

```json
{
  "commandline": "ffuf -w common.txt -u https://api.example.com/FUZZ -of json",
  "time": "2026-05-12T04:20:00Z",
  "results": [
    {
      "input": {"FUZZ": "admin"},
      "position": 0,
      "status": 200,
      "length": 1234,
      "words": 56,
      "lines": 12,
      "content-type": "text/html; charset=utf-8",
      "redirectlocation": "",
      "url": "https://api.example.com/admin",
      "host": "api.example.com"
    },
    {
      "input": {"FUZZ": "api"},
      "position": 1,
      "status": 401,
      "length": 64,
      "words": 5,
      "lines": 1,
      "content-type": "application/json",
      "redirectlocation": "",
      "url": "https://api.example.com/api",
      "host": "api.example.com"
    },
    {
      "input": {"FUZZ": "old"},
      "position": 2,
      "status": 301,
      "length": 0,
      "words": 0,
      "lines": 0,
      "content-type": "",
      "redirectlocation": "/new",
      "url": "https://api.example.com/old",
      "host": "api.example.com"
    }
  ]
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/recon/test_ffuf_tool.py
from __future__ import annotations

import json
from pathlib import Path

import pytest

from earn_money.recon import ffuf_tool


def test_approved_wordlists_constant_locked() -> None:
    """The approved set is the safety boundary — any change must be a
    conscious code-review event."""
    assert ffuf_tool.APPROVED_WORDLISTS == frozenset({
        "common.txt",
        "raft-medium-directories.txt",
    })


def test_build_command_includes_safety_flags(tmp_path: Path) -> None:
    wl = tmp_path / "common.txt"
    wl.write_text("admin\napi\n", encoding="utf-8")
    cmd = ffuf_tool.build_command(
        "https://api.example.com/",
        wordlist_path=wl,
        output_path=tmp_path / "ffuf-r1.json",
    )
    assert "-of" in cmd
    assert cmd[cmd.index("-of") + 1] == "json"
    assert "-t" in cmd and cmd[cmd.index("-t") + 1] == "10"
    assert "-rate" in cmd and cmd[cmd.index("-rate") + 1] == "50"
    assert "-timeout" in cmd and cmd[cmd.index("-timeout") + 1] == "10"
    assert "-mc" in cmd
    mc_value = cmd[cmd.index("-mc") + 1]
    assert set(mc_value.split(",")) == {"200", "204", "301", "302", "307", "401", "403"}
    assert "-fc" in cmd and cmd[cmd.index("-fc") + 1] == "404"
    assert "-ac" in cmd
    assert "-recursion" in cmd
    assert "-recursion-depth" in cmd and cmd[cmd.index("-recursion-depth") + 1] == "1"
    # The wordlist binding uses :FUZZ.
    assert "-w" in cmd
    assert cmd[cmd.index("-w") + 1] == f"{wl}:FUZZ"
    # Target is bound to FUZZ.
    assert "-u" in cmd
    assert cmd[cmd.index("-u") + 1] == "https://api.example.com/FUZZ"
    # No follow-redirects flag present.
    assert "-r" not in cmd


def test_build_command_rejects_unapproved_wordlist(tmp_path: Path) -> None:
    bad = tmp_path / "rockyou.txt"
    bad.write_text("x\n", encoding="utf-8")
    with pytest.raises(ffuf_tool.UnsafeWordlistProfile, match="rockyou.txt"):
        ffuf_tool.build_command(
            "https://api.example.com/",
            wordlist_path=bad,
            output_path=tmp_path / "out.json",
        )


def test_build_command_rejects_missing_wordlist(tmp_path: Path) -> None:
    """Even with an approved basename, a non-existent file must fail closed."""
    wl = tmp_path / "common.txt"  # NOT created
    with pytest.raises(ffuf_tool.UnsafeWordlistProfile, match="not found"):
        ffuf_tool.build_command(
            "https://api.example.com/",
            wordlist_path=wl,
            output_path=tmp_path / "out.json",
        )


def test_build_command_rejects_empty_target(tmp_path: Path) -> None:
    wl = tmp_path / "common.txt"
    wl.write_text("admin\n", encoding="utf-8")
    with pytest.raises(ValueError):
        ffuf_tool.build_command(
            "",
            wordlist_path=wl,
            output_path=tmp_path / "out.json",
        )


def test_build_command_appends_fuzz_to_target_without_trailing_slash(
    tmp_path: Path,
) -> None:
    wl = tmp_path / "common.txt"
    wl.write_text("admin\n", encoding="utf-8")
    cmd = ffuf_tool.build_command(
        "https://api.example.com",
        wordlist_path=wl,
        output_path=tmp_path / "out.json",
    )
    assert cmd[cmd.index("-u") + 1] == "https://api.example.com/FUZZ"


def test_parse_json_returns_signals(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "ffuf_output.json").read_text(encoding="utf-8")
    sigs = ffuf_tool.parse_json(
        raw, run_id="r1", observed_at="2026-05-12T04:30:00Z",
        target="https://api.example.com/",
    )
    assert len(sigs) == 3
    admin = next(s for s in sigs if "/admin" in s.signature)
    assert admin.signal_type == "content_match"
    assert admin.asset == "api.example.com"
    assert admin.target == "https://api.example.com/admin"
    assert admin.signature == "/admin|200|1-10KB|text/html"


def test_parse_json_payload_carries_status_and_length(fixtures_dir: Path) -> None:
    raw = (fixtures_dir / "ffuf_output.json").read_text(encoding="utf-8")
    sigs = ffuf_tool.parse_json(
        raw, run_id="r1", observed_at="t", target="https://api.example.com/",
    )
    api = next(s for s in sigs if "/api" in s.signature and "401" in s.signature)
    payload = json.loads(api.payload)
    assert payload["status"] == 401
    assert payload["length"] == 64
    assert payload["path"] == "/api"
    assert payload["content_type"] == "application/json"


def test_parse_json_handles_empty_results() -> None:
    raw = '{"commandline":"ffuf","time":"t","results":[]}'
    sigs = ffuf_tool.parse_json(
        raw, run_id="r1", observed_at="t", target="https://api.example.com/",
    )
    assert sigs == []


def test_parse_json_handles_malformed_json_returns_empty() -> None:
    """ffuf can crash mid-write and leave a half-written JSON file. Parser
    must not raise — caller (the runner) treats this as a source failure."""
    sigs = ffuf_tool.parse_json(
        "not-json", run_id="r1", observed_at="t",
        target="https://api.example.com/",
    )
    assert sigs == []


def test_parse_json_handles_redirect_signal(fixtures_dir: Path) -> None:
    """A 301 with redirect_location is a content_match with bucket=<1KB
    (length=0 ≤ 1024)."""
    raw = (fixtures_dir / "ffuf_output.json").read_text(encoding="utf-8")
    sigs = ffuf_tool.parse_json(
        raw, run_id="r1", observed_at="t", target="https://api.example.com/",
    )
    old = next(s for s in sigs if "/old" in s.signature)
    assert old.signature == "/old|301|<1KB|unknown"
    payload = json.loads(old.payload)
    assert payload["redirect_location"] == "/new"
```

- [ ] **Step 3: Verify RED**

```bash
.venv/bin/python -m pytest tests/recon/test_ffuf_tool.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 4: Implement the wrapper**

```python
# src/earn_money/recon/ffuf_tool.py
"""Subprocess wrapper around the Go-based `ffuf` CLI.

This wrapper is the safety boundary for ffuf. It refuses to build a
command whose wordlist basename is not in APPROVED_WORDLISTS, and it
forces the safety flags on every invocation (-mc, -fc, -ac, -t, -rate,
-timeout, -recursion-depth 1; no -r follow-redirects).

The wordlist allowlist is basename-based. The operator picks the
WORDLISTS_DIR via env var; the wrapper only validates that the file's
last path component is one of the approved names AND that the file
actually exists.

ffuf emits `-of json` as a single JSON object with a `results` array,
not JSONL. `parse_json` consumes the whole blob.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from earn_money.recon.signals import Signal
from earn_money.triage import hashing

APPROVED_WORDLISTS: frozenset[str] = frozenset({
    "common.txt",
    "raft-medium-directories.txt",
})

_MATCH_CODES: tuple[str, ...] = ("200", "204", "301", "302", "307", "401", "403")


class UnsafeWordlistProfile(Exception):
    """Raised when build_command is asked to use a non-approved wordlist."""


def build_command(
    target: str,
    *,
    wordlist_path: Path,
    output_path: Path,
) -> list[str]:
    if not target:
        raise ValueError("build_command requires a non-empty target")
    if wordlist_path.name not in APPROVED_WORDLISTS:
        raise UnsafeWordlistProfile(
            f"refusing to fuzz with non-approved wordlist {wordlist_path.name!r}. "
            f"Approved: {sorted(APPROVED_WORDLISTS)}"
        )
    if not wordlist_path.exists():
        raise UnsafeWordlistProfile(
            f"refusing to fuzz: wordlist {wordlist_path} not found on disk"
        )
    # Normalise the target so /FUZZ appends cleanly even if the caller
    # forgot the trailing slash.
    fuzz_url = target if target.endswith("/") else target + "/"
    fuzz_url = f"{fuzz_url}FUZZ"
    return [
        "ffuf",
        "-u", fuzz_url,
        "-w", f"{wordlist_path}:FUZZ",
        "-mc", ",".join(_MATCH_CODES),
        "-fc", "404",
        "-ac",
        "-t", "10",
        "-rate", "50",
        "-timeout", "10",
        "-recursion",
        "-recursion-depth", "1",
        "-of", "json",
        "-o", str(output_path),
    ]


def parse_json(
    raw: str, *, run_id: str, observed_at: str, target: str,
) -> list[Signal]:
    """Parse ffuf's `-of json` blob into Signal rows.

    Each results[] entry becomes one Signal with signal_type="content_match".
    Malformed or empty input returns []; the caller is responsible for
    treating that as a source failure if the run was expected to produce
    results.
    """
    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return []
    results = data.get("results") or []
    if not isinstance(results, list):
        return []

    asset_host = urlparse(target).hostname or ""
    out: list[Signal] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        try:
            out.append(
                _result_to_signal(
                    r, run_id=run_id, observed_at=observed_at, asset_host=asset_host,
                )
            )
        except (KeyError, ValueError):
            continue
    return out


def _result_to_signal(
    r: dict[str, Any],
    *,
    run_id: str,
    observed_at: str,
    asset_host: str,
) -> Signal:
    url = str(r.get("url") or "")
    if not url:
        raise ValueError("ffuf row has no url")
    status = int(r.get("status") or 0)
    length = int(r.get("length") or 0)
    content_type = str(r.get("content-type") or "")
    redirect_location = str(r.get("redirectlocation") or "")
    path = urlparse(url).path or "/"

    asset = hashing.normalize_asset(url) or asset_host
    target = hashing.normalize_target(url)
    signature = hashing.signature_for_ffuf(
        path=path, status_code=status,
        content_length=length, content_type=content_type,
    )
    payload = json.dumps({
        "path": path,
        "status": status,
        "length": length,
        "content_type": (content_type.split(";", 1)[0].strip().lower() or "unknown"),
        "redirect_location": redirect_location,
        "url": url,
    }, sort_keys=True)
    return Signal(
        run_id=run_id, tool="ffuf", signal_type="content_match",
        asset=asset, target=target, signature=signature,
        payload=payload, observed_at=observed_at,
    )
```

- [ ] **Step 5: Verify GREEN**

```bash
.venv/bin/python -m pytest tests/recon/test_ffuf_tool.py -v
make lint
```

Expected: 11 passed; lint clean.

- [ ] **Step 6: Commit**

```bash
git add src/earn_money/recon/ffuf_tool.py tests/recon/test_ffuf_tool.py \
        tests/fixtures/ffuf_output.json
git commit -m "feat: ffuf tool wrapper with approved wordlists + safety flags"
```

---

## Task 6: ffuf runner

The ffuf runner has a structural difference from nuclei/katana: ffuf's `-u <target>FUZZ` takes one target per invocation. We cannot batch multiple service URLs into a single subprocess.

Two consequences:

1. The runner iterates `service_urls` and runs one subprocess per URL.
2. Each subprocess produces one `-of json` blob written to a unique temp output file; the runner reads + parses each blob, accumulates `Signal` rows, and tallies per-host source failures.

The watchdog still wraps the entire loop (it polls `RECON_ENABLED` + the freeze flag every 5s, fires on state change). If the watchdog fires mid-loop, the in-flight subprocess gets SIGTERM and the loop breaks; the runner records `partial` + `terminated_reason="kill_switch"` (or `"freeze"`) and writes whatever artifacts the completed sub-runs produced.

We do **not** reuse `batch.run_batches` directly — its batch semantics assume "many targets per subprocess". Instead we use `subprocess.Popen` + `proc.communicate(timeout=...)` directly inside the runner, with the same watchdog event the batch helper exposes. The CLI module owns the watchdog wiring; the runner takes an injected `tool_run` callable that returns one `ToolRunResult` after iterating all targets.

**Per-host timeout:** 90 seconds per host (ffuf with a small wordlist + recursion-depth 1 typically finishes in 20-60s; 90s is the safety upper bound).

**Total run timeout:** the runner itself does not enforce a wall-clock on the whole loop — that's the systemd timer's job (`TimeoutStartSec=90min` per spec section 5). The watchdog is the in-process kill path.

**Files:**
- Create: `src/earn_money/runners/ffuf_scan.py`
- Create: `src/earn_money/runners/ffuf_scan_cli.py`
- Create: `tests/runners/test_ffuf_scan.py`

- [ ] **Step 1: Write the failing test (gate refusal + prereq missing)**

```python
# tests/runners/test_ffuf_scan.py
"""Tests for the ffuf-scan active-recon runner."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from earn_money import config, db, flags, policy, scope
from earn_money.recon import services, signals
from earn_money.runners import active, ffuf_scan


def _seed_scope(
    paths: config.Paths,
    *,
    policy_value: scope.Policy = "rate-limited-OK",
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope or ["*.example.com"],
        out_of_scope=out_of_scope or [],
        notes="", scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _seed_httpx_run_and_services(
    paths: config.Paths, *, services_to_insert: list[services.HttpService]
) -> None:
    from earn_money.recon import runs
    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        runs.start_run(
            conn, run_id="httpx-r1", platform="hackerone", slug="example",
            tool="httpx", started_at="2026-05-12T01:00:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-r1", finished_at="2026-05-12T01:05:00Z",
            status="success", output_count=len(services_to_insert),
            signal_count=0, source_failures=0, oos_drops=0,
        )
        for svc in services_to_insert:
            services.upsert_service(conn, svc)
    finally:
        conn.close()


def test_refuses_without_recon_enabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed_scope(paths)
    with pytest.raises(flags.ReconDisabled):
        ffuf_scan.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: active.ToolRunResult(outputs=()),
        )


def test_refuses_manual_only(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, policy_value="manual-only")
    with pytest.raises(policy.PolicyViolation):
        ffuf_scan.run_program(
            paths, "hackerone", "example",
            tool_run=lambda _targets: active.ToolRunResult(outputs=()),
        )


def test_writes_prereq_missing_signal_when_no_recent_httpx(
    tmp_repo: Path,
) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)

    result = ffuf_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _targets: active.ToolRunResult(outputs=()),
    )
    assert result.targets_scanned == 0
    assert result.signals_emitted == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT signal_type FROM signals WHERE tool = 'ffuf'"
    ).fetchall()
    run_status = conn.execute(
        "SELECT status, error_summary FROM recon_runs WHERE tool = 'ffuf'"
    ).fetchone()
    conn.close()
    assert rows == [("prereq_missing",)]
    assert run_status[0] == "skipped"
    assert "no recent httpx run" in run_status[1]
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/runners/test_ffuf_scan.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement the runner**

```python
# src/earn_money/runners/ffuf_scan.py
"""Content-discovery runner around ffuf.

ffuf's `-u <target>FUZZ` is per-host: one subprocess per service URL.
The runner therefore iterates the scoped service list and accumulates
results; batching across hosts is not possible.  The watchdog kill-switch
fires on `RECON_ENABLED` / `FROZEN` state changes between hosts and on
the in-flight subprocess via SIGTERM.

Per spec section 3, every emitted match is re-checked against scope on
both ``sig.asset`` AND ``target_host(sig.target, sig.asset)`` (imported from
``earn_money.recon.urls``).  Per spec section 7,
the runner refuses to scan if there is no recent successful httpx run
(prereq freshness check, 24h window).

CLI entry-point and real-tool wiring (incl. the per-host subprocess
loop) live in ffuf_scan_cli.py so this file stays under the 200-line cap.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from earn_money import config, db, scope
from earn_money.recon import runs, signals
from earn_money.recon.signals import Signal
from earn_money.recon.urls import target_host
from earn_money.runners import active

ToolRun = Callable[[list[str]], active.ToolRunResult]

_PREREQ_FRESHNESS_HOURS = 24


def _load_in_scope_service_urls(
    conn: sqlite3.Connection, s: scope.Scope
) -> list[str]:
    cursor = conn.execute(
        "SELECT url, subdomain FROM http_services "
        "WHERE in_scope_at_observation = 1 ORDER BY subdomain, scheme, port"
    )
    return [
        url for url, subdomain in cursor
        if scope.is_in_scope(subdomain, s.in_scope, s.out_of_scope)
    ]


def _recent_httpx_success(
    conn: sqlite3.Connection, *, platform: str, slug: str, now: datetime,
) -> bool:
    cutoff = (now - timedelta(hours=_PREREQ_FRESHNESS_HOURS)).isoformat(
        timespec="seconds"
    )
    row = conn.execute(
        "SELECT 1 FROM recon_runs WHERE platform = ? AND slug = ? "
        "AND tool = 'httpx' AND status IN ('success', 'partial') "
        "AND output_count > 0 "
        "AND finished_at IS NOT NULL AND finished_at >= ? LIMIT 1",
        (platform, slug, cutoff),
    ).fetchone()
    return row is not None


def _write_manifest(artifact_dir: Path, payload: dict[str, Any]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )


def _write_signals_jsonl(artifact_dir: Path, sigs: list[Signal]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with (artifact_dir / "signals.jsonl").open("w", encoding="utf-8") as fh:
        for s in sigs:
            fh.write(json.dumps({
                "tool": s.tool, "signal_type": s.signal_type,
                "asset": s.asset, "target": s.target,
                "signature": s.signature, "payload": s.payload,
                "observed_at": s.observed_at,
            }) + "\n")


def _write_required_artifacts(
    artifact_dir: Path,
    *,
    targets: list[str],
    raw_stdout: str,
    raw_stderr: str,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "input.txt").write_text(
        "\n".join(targets) + ("\n" if targets else ""), encoding="utf-8"
    )
    # ffuf emits JSON per host; raw_stdout is the concatenated blobs (one per
    # host, separated by a single newline) so the artifact remains
    # human-grep-able even though it isn't strictly JSONL.
    (artifact_dir / "raw.jsonl").write_text(raw_stdout, encoding="utf-8")
    (artifact_dir / "stderr.txt").write_text(raw_stderr, encoding="utf-8")


def run_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    tool_run: ToolRun,
    run_id: str | None = None,
) -> active.ActiveRunResult:
    """Gate-check → prereq freshness → load services → fuzz-per-host → filter → record."""
    s = active.check_gates(paths, platform, slug, mode="active")

    run_id = run_id or uuid.uuid4().hex
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat(timespec="seconds")
    artifact_dir = paths.root / (
        f"recon/outputs/{platform}/{slug}/ffuf/{now[:10]}/{run_id}"
    )

    conn = db.open_db(paths.program_db(platform, slug))
    try:
        if not _recent_httpx_success(conn, platform=platform, slug=slug, now=now_dt):
            return _record_prereq_missing(
                conn, platform, slug, run_id, now, artifact_dir,
            )

        targets = _load_in_scope_service_urls(conn, s)
        runs.start_run(
            conn, run_id=run_id, platform=platform, slug=slug, tool="ffuf",
            started_at=now, artifact_dir=str(artifact_dir), input_count=len(targets),
        )

        try:
            tool_result = (
                tool_run(targets) if targets
                else active.ToolRunResult(outputs=())
            )
        except Exception as exc:
            finished = datetime.now(UTC).isoformat(timespec="seconds")
            runs.finish_run(
                conn, run_id=run_id, finished_at=finished, status="failed",
                output_count=0, signal_count=0, source_failures=1, oos_drops=0,
                error_summary=f"{type(exc).__name__}: {exc}",
            )
            raise

        raw_signals: list[Signal] = list(tool_result.outputs)
        in_scope_sigs = [
            sig for sig in raw_signals
            if scope.is_in_scope(sig.asset, s.in_scope, s.out_of_scope)
            and scope.is_in_scope(
                target_host(sig.target, sig.asset), s.in_scope, s.out_of_scope,
            )
        ]
        oos_drops = len(raw_signals) - len(in_scope_sigs)

        if in_scope_sigs:
            signals.insert_signals(conn, in_scope_sigs)
        _write_signals_jsonl(artifact_dir, in_scope_sigs)
        _write_required_artifacts(
            artifact_dir,
            targets=targets,
            raw_stdout=tool_result.raw_stdout,
            raw_stderr=tool_result.raw_stderr,
        )
        _write_manifest(artifact_dir, {
            "run_id": run_id, "tool": "ffuf",
            "platform": platform, "slug": slug,
            "started_at": now, "input_count": len(targets),
            "signal_count": len(in_scope_sigs), "oos_drops": oos_drops,
        })

        terminated_reason: str | None = (
            tool_result.terminated_reason
            or ("kill_switch" if tool_result.aborted else None)
            or ("timeout" if tool_result.timed_out else None)
        )
        run_status = "partial" if terminated_reason else "success"

        finished = datetime.now(UTC).isoformat(timespec="seconds")
        runs.finish_run(
            conn, run_id=run_id, finished_at=finished, status=run_status,
            output_count=len(in_scope_sigs),
            signal_count=len(in_scope_sigs),
            source_failures=tool_result.source_failures, oos_drops=oos_drops,
            terminated_reason=terminated_reason,
        )
        return active.ActiveRunResult(
            run_id=run_id,
            targets_considered=len(targets),
            targets_scanned=len(targets),
            artifacts_written=1,
            signals_emitted=len(in_scope_sigs),
            source_failures=tool_result.source_failures,
            oos_drops=oos_drops,
        )
    finally:
        conn.close()


def _record_prereq_missing(
    conn: sqlite3.Connection,
    platform: str,
    slug: str,
    run_id: str,
    now: str,
    artifact_dir: Path,
) -> active.ActiveRunResult:
    runs.start_run(
        conn, run_id=run_id, platform=platform, slug=slug, tool="ffuf",
        started_at=now, artifact_dir=str(artifact_dir), input_count=0,
    )
    prereq_sig = Signal(
        run_id=run_id, tool="ffuf", signal_type="prereq_missing",
        asset="", target="",
        signature=f"prereq|httpx|<{_PREREQ_FRESHNESS_HOURS}h",
        payload=json.dumps({
            "required_tool": "httpx",
            "max_age_hours": _PREREQ_FRESHNESS_HOURS,
        }),
        observed_at=now,
    )
    signals.insert_signals(conn, [prereq_sig])
    _write_signals_jsonl(artifact_dir, [prereq_sig])
    _write_required_artifacts(artifact_dir, targets=[], raw_stdout="", raw_stderr="")
    _write_manifest(artifact_dir, {
        "run_id": run_id, "tool": "ffuf",
        "platform": platform, "slug": slug, "started_at": now,
        "status": "skipped", "reason": "no recent httpx run",
    })
    finished = datetime.now(UTC).isoformat(timespec="seconds")
    runs.finish_run(
        conn, run_id=run_id, finished_at=finished, status="skipped",
        output_count=0, signal_count=1, source_failures=0, oos_drops=0,
        error_summary="no recent httpx run within prereq freshness window",
    )
    return active.ActiveRunResult(
        run_id=run_id, targets_considered=0, targets_scanned=0,
        artifacts_written=1, signals_emitted=1, source_failures=0, oos_drops=0,
    )
```

The file lands at ~195 lines, under the cap.

- [ ] **Step 4: Implement `ffuf_scan_cli.py`**

```python
# src/earn_money/runners/ffuf_scan_cli.py
"""CLI entry-point and real-tool wiring for ffuf-scan.

ffuf is per-host (one subprocess per service URL).  The real-tool
function iterates `targets`, runs ffuf for each, parses the JSON output,
and accumulates Signals.  The kill-switch watchdog wraps the whole loop;
when it fires it sets `abort` and the loop breaks before the next host.

The WORDLISTS_DIR env var resolves to the on-disk location of the
approved wordlists.  In dev the operator points it at e.g.
/usr/share/seclists/Discovery/Web-Content; in CI/tests the e2e fixture
uses a tiny in-tree wordlist under tests/fixtures/ffuf_wordlists/.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from earn_money import config, flags, policy
from earn_money.recon import ffuf_tool
from earn_money.runners import active, ffuf_scan


_PER_HOST_TIMEOUT_S = 90.0
_DEFAULT_WORDLIST = "common.txt"


def _resolve_wordlist_path() -> Path:
    wordlists_dir = os.environ.get("WORDLISTS_DIR")
    if not wordlists_dir:
        raise ffuf_tool.UnsafeWordlistProfile(
            "WORDLISTS_DIR env var is not set; refusing to run ffuf"
        )
    return Path(wordlists_dir) / _DEFAULT_WORDLIST


def _build_real_tool(
    paths: config.Paths, platform: str, slug: str, run_id: str
) -> Callable[[list[str]], active.ToolRunResult]:
    """Wire the kill-switch watchdog + per-host subprocess + ffuf parser."""
    from earn_money.runners import watchdog

    def real_tool(targets: list[str]) -> active.ToolRunResult:
        wordlist = _resolve_wordlist_path()
        abort = threading.Event()
        abort_reason: list[str | None] = [None]

        def on_state_change(reason: str) -> None:
            abort_reason[0] = reason
            abort.set()

        wd = watchdog.KillSwitchWatchdog(
            paths, platform=platform, slug=slug,
            on_state_change=on_state_change,
            poll_interval_s=5.0,
        )
        wd.start()

        collected_signals: list = []
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        source_failures = 0
        timed_out_any = False

        try:
            with tempfile.TemporaryDirectory() as td_str:
                td = Path(td_str)
                for idx, target in enumerate(targets):
                    if abort.is_set():
                        break
                    out_path = td / f"ffuf-{idx}.json"
                    try:
                        cmd = ffuf_tool.build_command(
                            target, wordlist_path=wordlist, output_path=out_path,
                        )
                    except ffuf_tool.UnsafeWordlistProfile:
                        # Fail closed: re-raise so the outer try/except in the
                        # runner records the run as `failed`.
                        raise
                    proc = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    )
                    try:
                        out, err = proc.communicate(timeout=_PER_HOST_TIMEOUT_S)
                        host_timed_out = False
                    except subprocess.TimeoutExpired:
                        proc.terminate()
                        try:
                            out, err = proc.communicate(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            out, err = proc.communicate()
                        host_timed_out = True
                    stdout_chunks.append(out or "")
                    stderr_chunks.append(err or "")
                    if host_timed_out or proc.returncode not in (0, None):
                        source_failures += 1
                    timed_out_any = timed_out_any or host_timed_out
                    # Parse the JSON output file (ffuf writes it before exit
                    # for completed runs).
                    if out_path.exists():
                        raw = out_path.read_text(encoding="utf-8")
                        now = datetime.now(UTC).isoformat(timespec="seconds")
                        collected_signals.extend(
                            ffuf_tool.parse_json(
                                raw, run_id=run_id, observed_at=now, target=target,
                            )
                        )
        finally:
            wd.stop()

        raw_stdout = "\n".join(stdout_chunks)
        raw_stderr = "\n".join(stderr_chunks)
        return active.ToolRunResult(
            outputs=tuple(collected_signals),
            aborted=abort.is_set(),
            terminated_reason=abort_reason[0],
            source_failures=source_failures,
            timed_out=timed_out_any,
            raw_stdout=raw_stdout,
            raw_stderr=raw_stderr,
        )

    return real_tool


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ffuf-scan")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    args = parser.parse_args(argv)

    paths = config.Paths.from_root(args.root)
    run_id = uuid.uuid4().hex
    real_tool = _build_real_tool(
        paths, platform=args.platform, slug=args.program, run_id=run_id
    )

    try:
        result = ffuf_scan.run_program(
            paths, args.platform, args.program,
            tool_run=real_tool, run_id=run_id,
        )
    except flags.ReconDisabled as e:
        print(f"ffuf-scan: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"ffuf-scan: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"ffuf-scan: {e}", file=sys.stderr)
        return 4
    except ffuf_tool.UnsafeWordlistProfile as e:
        print(f"ffuf-scan: {e}", file=sys.stderr)
        return 5
    except Exception as e:
        print(
            f"ffuf-scan: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    print(
        f"ffuf-scan: scanned={result.targets_scanned} "
        f"signals={result.signals_emitted} "
        f"oos_drops={result.oos_drops} "
        f"source_failures={result.source_failures}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

This CLI module lands at ~190 lines — just under the cap. If a future commit adds more logic, extract the per-host subprocess loop to a private `_ffuf_loop.py` helper.

- [ ] **Step 5: Verify the gate + prereq tests GREEN**

```bash
.venv/bin/python -m pytest tests/runners/test_ffuf_scan.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Write the happy-path test (writes signals + all 5 artifacts)**

```python
# tests/runners/test_ffuf_scan.py — append

def test_writes_signals_for_in_scope_services(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])

    _seed_httpx_run_and_services(
        paths, services_to_insert=[
            services.HttpService(
                subdomain="api.example.com", scheme="https", port=443,
                url="https://api.example.com/", status_code=200, title=None,
                server=None, technologies=(), redirect_to=None, tls_summary=None,
                observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
            ),
        ],
    )

    captured_targets: list[list[str]] = []

    def fake_tool(targets: list[str]) -> active.ToolRunResult:
        captured_targets.append(list(targets))
        return active.ToolRunResult(outputs=(
            signals.Signal(
                run_id="r", tool="ffuf", signal_type="content_match",
                asset="api.example.com",
                target="https://api.example.com/admin",
                signature="/admin|200|1-10KB|text/html",
                payload='{"path":"/admin","status":200,"length":1234,"content_type":"text/html"}',
                observed_at="2026-05-12T04:21:00Z",
            ),
        ))

    result = ffuf_scan.run_program(
        paths, "hackerone", "example", tool_run=fake_tool,
        run_id="ffuf-r1",
    )
    assert result.signals_emitted == 1
    assert result.oos_drops == 0
    assert captured_targets == [["https://api.example.com/"]]

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    sigs = conn.execute(
        "SELECT signal_type, asset, signature FROM signals WHERE tool = 'ffuf'"
    ).fetchall()
    runs_rows = conn.execute(
        "SELECT status FROM recon_runs WHERE tool = 'ffuf'"
    ).fetchall()
    conn.close()
    assert sigs == [("content_match", "api.example.com", "/admin|200|1-10KB|text/html")]
    assert runs_rows == [("success",)]

    # All 5 required artifact files exist.
    ffuf_out = (
        paths.root / "recon" / "outputs" / "hackerone" / "example" / "ffuf"
    )
    assert len(list(ffuf_out.rglob("manifest.json"))) == 1
    assert len(list(ffuf_out.rglob("signals.jsonl"))) == 1
    assert len(list(ffuf_out.rglob("input.txt"))) == 1
    assert len(list(ffuf_out.rglob("raw.jsonl"))) == 1
    assert len(list(ffuf_out.rglob("stderr.txt"))) == 1
```

Run + verify GREEN.

- [ ] **Step 7: Write the OOS dual-key drop tests**

```python
# tests/runners/test_ffuf_scan.py — append

def test_drops_oos_signals_from_tool_output(tmp_repo: Path) -> None:
    """A signal whose sig.asset resolves OOS must be dropped."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def leaky_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(
            signals.Signal(
                run_id="r", tool="ffuf", signal_type="content_match",
                asset="api.example.com", target="https://api.example.com/admin",
                signature="/admin|200|<1KB|text/html", payload="{}", observed_at="t",
            ),
            signals.Signal(
                run_id="r", tool="ffuf", signal_type="content_match",
                asset="evil.example.com", target="https://evil.example.com/admin",
                signature="/admin|200|<1KB|text/html", payload="{}", observed_at="t",
            ),
        ))

    result = ffuf_scan.run_program(
        paths, "hackerone", "example", tool_run=leaky_tool,
    )
    assert result.signals_emitted == 1
    assert result.oos_drops == 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute(
        "SELECT asset FROM signals WHERE tool = 'ffuf'"
    ).fetchall()
    conn.close()
    assert rows == [("api.example.com",)]


def test_drops_signals_with_oos_target_even_if_asset_in_scope(
    tmp_repo: Path,
) -> None:
    """Dual-key filter: in-scope asset, OOS target URL → dropped."""
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def leaky_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(outputs=(
            signals.Signal(
                run_id="r", tool="ffuf", signal_type="content_match",
                asset="api.example.com",  # in-scope asset
                target="https://evil.example.com/leaked",  # OOS target!
                signature="/leaked|200|<1KB|text/html",
                payload="{}", observed_at="t",
            ),
        ))

    result = ffuf_scan.run_program(
        paths, "hackerone", "example", tool_run=leaky_tool,
    )
    assert result.oos_drops == 1
    assert result.signals_emitted == 0
```

Run + verify GREEN.

- [ ] **Step 8: Write the prereq-still-writes-artifacts test**

```python
# tests/runners/test_ffuf_scan.py — append

def test_prereq_missing_still_writes_required_artifacts(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths)

    result = ffuf_scan.run_program(
        paths, "hackerone", "example",
        tool_run=lambda _targets: active.ToolRunResult(outputs=()),
    )
    assert result.signals_emitted == 1

    ffuf_out = paths.root / "recon" / "outputs" / "hackerone" / "example" / "ffuf"
    for name in ("manifest.json", "signals.jsonl", "input.txt", "raw.jsonl", "stderr.txt"):
        files = list(ffuf_out.rglob(name))
        assert len(files) == 1, f"missing required artifact: {name}"
```

Run + verify GREEN.

- [ ] **Step 9: Write the watchdog terminated_reason capture test**

```python
# tests/runners/test_ffuf_scan.py — append

def test_records_terminated_reason_from_tool_result(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed_scope(paths, in_scope=["api.example.com"])
    _seed_httpx_run_and_services(paths, services_to_insert=[
        services.HttpService(
            subdomain="api.example.com", scheme="https", port=443,
            url="https://api.example.com/", status_code=200, title=None,
            server=None, technologies=(), redirect_to=None, tls_summary=None,
            observed_at="t", last_run_id="httpx-r1", in_scope_at_observation=True,
        ),
    ])

    def aborted_tool(_targets: list[str]) -> active.ToolRunResult:
        return active.ToolRunResult(
            outputs=(),
            aborted=True,
            terminated_reason="freeze",
        )

    result = ffuf_scan.run_program(
        paths, "hackerone", "example", tool_run=aborted_tool,
    )
    assert result.signals_emitted == 0

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    row = conn.execute(
        "SELECT status, terminated_reason FROM recon_runs WHERE tool = 'ffuf'"
    ).fetchone()
    conn.close()
    assert row == ("partial", "freeze")
```

Run + verify GREEN.

- [ ] **Step 10: Lint**

```bash
make lint
```

- [ ] **Step 11: Commit**

```bash
git add src/earn_money/runners/ffuf_scan.py \
        src/earn_money/runners/ffuf_scan_cli.py \
        tests/runners/test_ffuf_scan.py
git commit -m "feat: ffuf-scan runner with approved wordlists + per-host loop"
```

---

## Task 7: Triage classify dispatch for katana + ffuf

`src/earn_money/triage/classify.py` already dispatches `(nuclei, template_match)`, `(nuclei, prereq_missing)`, and `(httpx, fingerprint_drift)`. Phase 3c adds two new branches.

**Branch: `(katana, endpoint_discovered)`**

- `vuln_class = "recon-endpoint"` — this is a discovery signal, not a vuln class per se; triage groups all katana hits under one class so the queue can rank them as a single batch.
- `severity_hint = "info"` — discovery is informational by definition.
- `confidence = 30` — low confidence; the operator must verify a discovered endpoint is interesting before triage.
- `title = f"katana discovered endpoint on {sig.asset}"`.

**Branch: `(ffuf, content_match)`**

Status code drives the heuristic per the spec section 3.4 ("interesting responses"):

- `200` / `204` / `301` / `302` / `307`: probably-public content. `severity_hint="info"`, `confidence` from status code (`200=50, 30x=30`).
- `401` / `403`: possible auth gate. `severity_hint="low"`, `confidence=70` because the path exists but is protected — these are the most interesting ffuf hits and often surface auth-bypass paths or stale endpoints with weak controls.

- `vuln_class = "recon-content"`
- `title = f"ffuf found {payload.path} on {sig.asset}"` — uses the path from the signal payload.

Both branches consume `sig.payload` (compact JSON) to extract supporting fields when needed.

Phase 3b shipped `classify.py` without a dedicated test file (the engine tests covered the nuclei branch end-to-end). 3c creates `tests/triage/test_classify.py` because:

1. Direct branch tests are faster to iterate than re-running the full triage engine in a tmp_repo.
2. Mirrors the file layout convention (one test module per source module).
3. Backfills coverage for the existing 3b branches that were only ever exercised by the engine tests.

**Files:**
- Modify: `src/earn_money/triage/classify.py`
- Create: `tests/triage/test_classify.py`

- [ ] **Step 1: Write the failing test file**

```python
# tests/triage/test_classify.py
from __future__ import annotations

from earn_money.recon.signals import Signal
from earn_money.triage import classify


def _sig(
    *,
    tool: str,
    signal_type: str,
    asset: str = "api.example.com",
    target: str = "https://api.example.com/",
    payload: str = "{}",
) -> Signal:
    return Signal(
        run_id="r", tool=tool, signal_type=signal_type,
        asset=asset, target=target, signature="sig",
        payload=payload, observed_at="t",
    )


def test_classify_nuclei_template_match_uses_payload_severity() -> None:
    sig = _sig(
        tool="nuclei", signal_type="template_match",
        payload='{"template_id":"CVE-2023-1234","severity":"high","name":"Acme SQLi"}',
    )
    vuln_class, title, severity, confidence = classify.classify(sig)
    assert vuln_class == "cve-2023-1234"
    assert "Acme SQLi" in title
    assert severity == "high"
    assert confidence == 70


def test_classify_nuclei_prereq_missing_is_factual_info() -> None:
    sig = _sig(tool="nuclei", signal_type="prereq_missing", asset="", target="")
    vuln_class, _title, severity, confidence = classify.classify(sig)
    assert vuln_class == "recon-prereq-missing"
    assert severity == "info"
    assert confidence == 100


def test_classify_httpx_fingerprint_drift() -> None:
    sig = _sig(tool="httpx", signal_type="fingerprint_drift")
    vuln_class, title, severity, confidence = classify.classify(sig)
    assert vuln_class == "recon-fingerprint-drift"
    assert "api.example.com" in title
    assert severity == "info"
    assert confidence == 40


def test_classify_katana_endpoint_discovered() -> None:
    sig = _sig(
        tool="katana", signal_type="endpoint_discovered",
        target="https://api.example.com/admin/dashboard",
        payload='{"method":"GET","endpoint":"https://api.example.com/admin/dashboard"}',
    )
    vuln_class, title, severity, confidence = classify.classify(sig)
    assert vuln_class == "recon-endpoint"
    assert "katana discovered endpoint" in title
    assert "api.example.com" in title
    assert severity == "info"
    assert confidence == 30


def test_classify_ffuf_content_match_200_is_info() -> None:
    sig = _sig(
        tool="ffuf", signal_type="content_match",
        payload='{"path":"/admin","status":200,"length":1234,"content_type":"text/html"}',
    )
    vuln_class, title, severity, confidence = classify.classify(sig)
    assert vuln_class == "recon-content"
    assert "/admin" in title
    assert severity == "info"
    assert confidence == 50


def test_classify_ffuf_content_match_30x_is_info_low_confidence() -> None:
    """301/302/307: probably-public-but-redirected. Lower confidence than 200."""
    for status in (301, 302, 307):
        sig = _sig(
            tool="ffuf", signal_type="content_match",
            payload='{"path":"/old","status":' + str(status) + ',"length":0,"content_type":""}',
        )
        _vc, _title, severity, confidence = classify.classify(sig)
        assert severity == "info", f"status {status}: expected info, got {severity}"
        assert confidence == 30, f"status {status}: expected 30, got {confidence}"


def test_classify_ffuf_content_match_401_403_is_low_with_high_confidence() -> None:
    """4xx auth-gate codes are the most interesting ffuf hits — flag as low
    severity so the digest ranks them above plain discovery."""
    for status in (401, 403):
        sig = _sig(
            tool="ffuf", signal_type="content_match",
            payload='{"path":"/internal","status":' + str(status) + ',"length":64,"content_type":"application/json"}',
        )
        _vc, _title, severity, confidence = classify.classify(sig)
        assert severity == "low", f"status {status}: expected low, got {severity}"
        assert confidence == 70, f"status {status}: expected 70, got {confidence}"


def test_classify_ffuf_content_match_with_unparseable_payload_falls_back() -> None:
    """Bad payload JSON must not crash the classifier."""
    sig = _sig(
        tool="ffuf", signal_type="content_match",
        payload="not-json",
    )
    vuln_class, _title, severity, confidence = classify.classify(sig)
    assert vuln_class == "recon-content"
    assert severity == "info"
    # confidence falls back to 30 (unknown status → default).
    assert confidence == 30


def test_classify_unknown_tool_signal_returns_recon_other() -> None:
    sig = _sig(tool="mystery", signal_type="weird")
    vuln_class, _title, severity, confidence = classify.classify(sig)
    assert vuln_class == "recon-other"
    assert severity == "unknown"
    assert confidence == 0
```

- [ ] **Step 2: Verify RED**

```bash
.venv/bin/python -m pytest tests/triage/test_classify.py -v
```

Expected: the existing-branch tests (nuclei + httpx) pass; the katana + ffuf tests fail with `AssertionError: 'recon-endpoint' != 'recon-other'`.

- [ ] **Step 3: Implement the new branches**

```python
# src/earn_money/triage/classify.py — extend
"""Signal classification dispatch: derives (vuln_class, title, severity_hint,
confidence) from a Signal's tool + signal_type + payload.

Keeping this module separate from the engine keeps both files under the
200-line cap and makes the dispatch table easy to extend.
"""

from __future__ import annotations

import json
from typing import Any

from earn_money.recon.signals import Signal

# Return type alias: (vuln_class, title, severity_hint, confidence)
Classification = tuple[str, str, str, int]

_SEVERITY_CONFIDENCE: dict[str, int] = {
    "critical": 80,
    "high": 70,
    "medium": 50,
    "low": 35,
    "info": 30,
}

# Per-status-code confidence for ffuf content matches.
_FFUF_STATUS_CONFIDENCE: dict[int, int] = {
    200: 50,
    204: 50,
    301: 30,
    302: 30,
    307: 30,
    401: 70,  # auth gate — most interesting class of ffuf hit
    403: 70,
}

_FFUF_AUTH_CODES: frozenset[int] = frozenset({401, 403})


def classify(sig: Signal) -> Classification:
    """Derive (vuln_class, title, severity_hint, confidence) from a signal."""
    if sig.tool == "nuclei" and sig.signal_type == "template_match":
        return _classify_nuclei_match(sig)
    if sig.tool == "nuclei" and sig.signal_type == "prereq_missing":
        return (
            "recon-prereq-missing",
            "nuclei skipped: no recent httpx run",
            "info",
            100,
        )
    if sig.tool == "httpx" and sig.signal_type == "fingerprint_drift":
        return (
            "recon-fingerprint-drift",
            f"httpx fingerprint changed on {sig.asset}",
            "info",
            40,
        )
    if sig.tool == "katana" and sig.signal_type == "endpoint_discovered":
        return (
            "recon-endpoint",
            f"katana discovered endpoint on {sig.asset}",
            "info",
            30,
        )
    if sig.tool == "ffuf" and sig.signal_type == "content_match":
        return _classify_ffuf_content(sig)
    return (
        "recon-other",
        f"{sig.tool}/{sig.signal_type} on {sig.asset}",
        "unknown",
        0,
    )


def _classify_nuclei_match(sig: Signal) -> Classification:
    try:
        payload: dict[str, Any] = json.loads(sig.payload)
    except json.JSONDecodeError:
        payload = {}
    template_id = str(payload.get("template_id", "unknown")).lower()
    severity = str(payload.get("severity", "unknown")).lower()
    name = str(payload.get("name") or template_id)
    confidence = _SEVERITY_CONFIDENCE.get(severity, 30)
    title = f"{name} on {sig.asset}"
    return (template_id, title, severity, confidence)


def _classify_ffuf_content(sig: Signal) -> Classification:
    try:
        payload: dict[str, Any] = json.loads(sig.payload)
    except json.JSONDecodeError:
        payload = {}
    path = str(payload.get("path") or "/")
    status = int(payload.get("status") or 0)
    if status in _FFUF_AUTH_CODES:
        severity = "low"
    else:
        severity = "info"
    confidence = _FFUF_STATUS_CONFIDENCE.get(status, 30)
    title = f"ffuf found {path} on {sig.asset}"
    return ("recon-content", title, severity, confidence)
```

- [ ] **Step 4: Verify GREEN**

```bash
.venv/bin/python -m pytest tests/triage/test_classify.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Re-run the engine tests to confirm the new branches integrate**

```bash
.venv/bin/python -m pytest tests/triage/ -v
```

Expected: all triage tests (hashing + findings + history + queue + engine + classify) pass.

- [ ] **Step 6: Lint**

```bash
make lint
```

- [ ] **Step 7: Commit**

```bash
git add src/earn_money/triage/classify.py tests/triage/test_classify.py
git commit -m "feat: triage classify branches for katana + ffuf"
```

---

## Task 8: `bin/ffuf-scan` CLI

Same shape as `bin/katana-crawl` and `bin/nuclei-scan`.

**Files:**
- Create: `bin/ffuf-scan`

- [ ] **Step 1: Write the script**

```sh
#!/bin/sh
# Thin wrapper around the ffuf-scan runner.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/.env"
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "ffuf-scan: .venv not found at $ROOT/.venv — run 'make install-dev' first" >&2
  exit 1
fi

exec "$ROOT/.venv/bin/python" -m earn_money.runners.ffuf_scan_cli --root "$ROOT" "$@"
```

- [ ] **Step 2: Make executable and verify**

```bash
chmod +x bin/ffuf-scan
bin/ffuf-scan --help
```

Expected: argparse usage line for `ffuf-scan`.

- [ ] **Step 3: Commit**

```bash
git add bin/ffuf-scan
git commit -m "feat: bin/ffuf-scan CLI wrapper"
```

---

## Task 9: End-to-end integration tests for katana and ffuf

Two smoke tests that exercise the real binaries against the mock target:

1. **`test_katana_scan_e2e.py`** — invokes the real `katana` binary against the in-tree mock target (port 18081). Auto-skips when binary is absent. Asserts: at least one `Signal` row, `signals.jsonl` artifact, manifest written.

2. **`test_ffuf_scan_e2e.py`** — invokes the real `ffuf` binary against the mock target with a tiny in-tree wordlist that contains paths the mock target serves. Auto-skips when binary is absent OR when the in-tree wordlist file is absent.

For ffuf, the wordlist is intentionally small and lives at `tests/fixtures/ffuf_wordlists/tiny.txt`. Its basename is `tiny.txt`, which is **not** in `APPROVED_WORDLISTS`. To make the e2e test work without weakening the production safety boundary, the test temporarily monkeypatches `ffuf_tool.APPROVED_WORDLISTS` to include `"tiny.txt"`. This is the same pattern Phase 3b uses for the nuclei e2e (`build_unsafe`) — fixture-only relaxations gated behind a test seam.

The mock target needs a few extra paths to make ffuf produce interesting hits. We extend `tests/fixtures/mock_target/server.py` minimally — wait, that's a 3b file and we should NOT touch it without justification. Instead, the test asserts ffuf returns whatever the mock target serves at port 18081 (`/` → 200 "In-Scope A"). The wordlist contains entries that mostly miss (404), but at least the empty/root entry hits 200. We assert ≥1 content_match was emitted from the wordlist's matches against the live mock target.

(If a future operator wants richer ffuf coverage in the e2e, they can extend the mock-target handler in a separate commit and add a wordlist entry that matches the new path — but the contract here is just "ffuf produces at least one match against the mock target", which is enough to prove the parser, watchdog, and artifact path work end-to-end.)

**Files:**
- Create: `tests/runners/test_katana_scan_e2e.py`
- Create: `tests/runners/test_ffuf_scan_e2e.py`
- Create: `tests/fixtures/ffuf_wordlists/tiny.txt`

- [ ] **Step 1: Write the tiny wordlist**

`tests/fixtures/ffuf_wordlists/tiny.txt`:

```
admin
api
login
robots.txt
index
```

(Five lines. The mock target returns 200 to `/` — but ffuf appends each word to the URL, so `/admin`, `/api`, etc. The mock target's `_InScopeHandler` returns 200 for **every** GET, so each entry produces a 200 match. This gives ffuf 5 results, which is more than enough to prove the parse + artifact path.)

- [ ] **Step 2: Write the katana e2e test**

```python
# tests/runners/test_katana_scan_e2e.py
"""End-to-end katana smoke against the mock target.

Auto-skips when the katana binary is not on PATH or the mock target
fixture is unavailable.

We use the production build_command path (the crawl caps are not
relaxed in tests). The mock target's surface is small enough that a
single shallow crawl exits in well under MAX_DURATION_S.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import threading
import uuid
from pathlib import Path

import pytest

from earn_money import config, db, scope
from earn_money.recon import katana_tool, runs, services
from earn_money.recon.services import HttpService
from earn_money.runners import active, batch, katana_scan


_KATANA = shutil.which("katana")

pytestmark = pytest.mark.skipif(
    not _KATANA,
    reason="ProjectDiscovery katana binary not present on PATH",
)


def _seed(tmp_repo: Path) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["127.0.0.1"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        services.upsert_service(conn, HttpService(
            subdomain="127.0.0.1", scheme="http", port=18081,
            url="http://127.0.0.1:18081/", status_code=200,
            title="In-Scope A", server="mock-target/1.0",
            technologies=(), redirect_to=None, tls_summary=None,
            observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
            in_scope_at_observation=True,
        ))
        runs.start_run(
            conn, run_id="httpx-r1", platform="hackerone", slug="example",
            tool="httpx", started_at="2026-05-12T01:00:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-r1", finished_at="2026-05-12T01:05:00Z",
            status="success", output_count=1, signal_count=0,
            source_failures=0, oos_drops=0,
        )
    finally:
        conn.close()
    return paths


def _make_tool_run(monkeypatch: pytest.MonkeyPatch, run_id: str):  # type: ignore[type-arg]
    katana_path = Path(_KATANA)  # type: ignore[arg-type]
    pd_bin_dir = str(katana_path.parent)
    current_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{pd_bin_dir}:{current_path}")

    def tool_run(targets: list[str]) -> active.ToolRunResult:
        abort = threading.Event()
        # No watchdog inside the test; e2e uses the production build_command
        # but bypasses the full CLI wiring for speed.
        result = batch.run_batches(
            targets,
            command_factory=lambda chunk: katana_tool.build_command(
                chunk,
                depth=1,                # shallow; mock target is tiny
                duration_s=60,          # cap at 60s for the test
                max_urls=100,
            ),
            max_batch_size=50,
            max_batch_duration_s=120.0,
            abort=abort,
        )
        raw = "\n".join(line for b in result.batches for line in b.lines)
        parsed = katana_tool.parse_jsonl(raw, run_id=run_id, observed_at="t")
        return active.ToolRunResult(
            outputs=tuple(parsed),
            aborted=result.aborted,
        )

    return tool_run


def test_e2e_katana_writes_signal_against_mock_target(
    tmp_repo: Path, mock_target: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _seed(tmp_repo)
    run_id = uuid.uuid4().hex
    tool_run = _make_tool_run(monkeypatch, run_id)

    result = katana_scan.run_program(
        paths, "hackerone", "example", tool_run=tool_run, run_id=run_id,
    )
    # The mock target serves a single static page; katana should at minimum
    # report the root URL it was given.
    assert result.signals_emitted >= 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    sigs = conn.execute(
        "SELECT signal_type, asset FROM signals WHERE tool = 'katana'"
    ).fetchall()
    runs_rows = conn.execute(
        "SELECT status FROM recon_runs WHERE tool = 'katana'"
    ).fetchall()
    conn.close()
    assert runs_rows == [("success",)]
    assert all(stype == "endpoint_discovered" for stype, _asset in sigs)

    # Artifact files exist.
    katana_out = (
        paths.root / "recon" / "outputs" / "hackerone" / "example" / "katana"
    )
    manifests = list(katana_out.rglob("manifest.json"))
    assert len(manifests) == 1
    sig_files = list(katana_out.rglob("signals.jsonl"))
    assert len(sig_files) == 1
    sig_lines = [ln for ln in sig_files[0].read_text(encoding="utf-8").splitlines() if ln]
    assert any(
        json.loads(ln)["signal_type"] == "endpoint_discovered" for ln in sig_lines
    )
```

- [ ] **Step 3: Verify the katana e2e**

```bash
.venv/bin/python -m pytest tests/runners/test_katana_scan_e2e.py -v
```

Expected: 1 skipped on hosts without katana; 1 passed on the VPS.

- [ ] **Step 4: Write the ffuf e2e test**

```python
# tests/runners/test_ffuf_scan_e2e.py
"""End-to-end ffuf smoke against the mock target.

Auto-skips when:
- The ffuf binary is not on PATH
- The tiny wordlist fixture is absent

The test temporarily monkeypatches ffuf_tool.APPROVED_WORDLISTS to
include "tiny.txt" so the e2e can use the in-tree fixture without
weakening the production allowlist.  Same pattern as Phase 3b's nuclei
e2e (build_unsafe).
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

from earn_money import config, db, scope
from earn_money.recon import ffuf_tool, runs, services
from earn_money.recon.services import HttpService
from earn_money.runners import active, ffuf_scan


_FFUF = shutil.which("ffuf")
_WORDLIST = (
    Path(__file__).parent.parent
    / "fixtures" / "ffuf_wordlists" / "tiny.txt"
)

pytestmark = pytest.mark.skipif(
    not _FFUF or not _WORDLIST.exists(),
    reason="ffuf binary or tiny wordlist fixture not present",
)


def _seed(tmp_repo: Path) -> config.Paths:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    s = scope.Scope(
        platform="hackerone", slug="example", policy="rate-limited-OK",
        in_scope=["127.0.0.1"], out_of_scope=[],
        notes="", scope_hash="seed", last_synced="t",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)

    conn = db.open_db(paths.program_db("hackerone", "example"))
    try:
        services.upsert_service(conn, HttpService(
            subdomain="127.0.0.1", scheme="http", port=18081,
            url="http://127.0.0.1:18081/", status_code=200,
            title="In-Scope A", server="mock-target/1.0",
            technologies=(), redirect_to=None, tls_summary=None,
            observed_at="2026-05-12T01:05:00Z", last_run_id="httpx-r1",
            in_scope_at_observation=True,
        ))
        runs.start_run(
            conn, run_id="httpx-r1", platform="hackerone", slug="example",
            tool="httpx", started_at="2026-05-12T01:00:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="httpx-r1", finished_at="2026-05-12T01:05:00Z",
            status="success", output_count=1, signal_count=0,
            source_failures=0, oos_drops=0,
        )
    finally:
        conn.close()
    return paths


def _make_tool_run(monkeypatch: pytest.MonkeyPatch, run_id: str):  # type: ignore[type-arg]
    """Per-host ffuf loop with the wordlist fixture.

    We monkeypatch APPROVED_WORDLISTS to include the test wordlist name so
    build_command accepts the fixture path. Production callers see the
    unmonkeypatched allowlist.
    """
    ffuf_path = Path(_FFUF)  # type: ignore[arg-type]
    pd_bin_dir = str(ffuf_path.parent)
    current_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{pd_bin_dir}:{current_path}")
    monkeypatch.setattr(
        ffuf_tool, "APPROVED_WORDLISTS",
        ffuf_tool.APPROVED_WORDLISTS | {"tiny.txt"},
    )

    def tool_run(targets: list[str]) -> active.ToolRunResult:
        collected: list = []
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        source_failures = 0
        with tempfile.TemporaryDirectory() as td_str:
            td = Path(td_str)
            for idx, target in enumerate(targets):
                out_path = td / f"ffuf-{idx}.json"
                cmd = ffuf_tool.build_command(
                    target, wordlist_path=_WORDLIST, output_path=out_path,
                )
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                try:
                    out, err = proc.communicate(timeout=60)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    out, err = proc.communicate()
                    source_failures += 1
                stdout_chunks.append(out or "")
                stderr_chunks.append(err or "")
                if proc.returncode not in (0, None):
                    source_failures += 1
                if out_path.exists():
                    raw = out_path.read_text(encoding="utf-8")
                    collected.extend(
                        ffuf_tool.parse_json(
                            raw, run_id=run_id, observed_at="t", target=target,
                        )
                    )
        return active.ToolRunResult(
            outputs=tuple(collected),
            source_failures=source_failures,
            raw_stdout="\n".join(stdout_chunks),
            raw_stderr="\n".join(stderr_chunks),
        )

    return tool_run


def test_e2e_ffuf_writes_signal_against_mock_target(
    tmp_repo: Path, mock_target: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _seed(tmp_repo)
    run_id = uuid.uuid4().hex
    tool_run = _make_tool_run(monkeypatch, run_id)

    result = ffuf_scan.run_program(
        paths, "hackerone", "example", tool_run=tool_run, run_id=run_id,
    )
    # The mock target returns 200 for every path; ffuf should produce ≥1
    # content_match.
    assert result.signals_emitted >= 1

    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    sigs = conn.execute(
        "SELECT signal_type, asset FROM signals WHERE tool = 'ffuf'"
    ).fetchall()
    runs_rows = conn.execute(
        "SELECT status FROM recon_runs WHERE tool = 'ffuf'"
    ).fetchall()
    conn.close()
    assert runs_rows == [("success",)]
    assert all(stype == "content_match" for stype, _asset in sigs)

    # Artifact files exist.
    ffuf_out = (
        paths.root / "recon" / "outputs" / "hackerone" / "example" / "ffuf"
    )
    manifests = list(ffuf_out.rglob("manifest.json"))
    assert len(manifests) == 1
    sig_files = list(ffuf_out.rglob("signals.jsonl"))
    assert len(sig_files) == 1
    sig_lines = [ln for ln in sig_files[0].read_text(encoding="utf-8").splitlines() if ln]
    assert any(
        json.loads(ln)["signal_type"] == "content_match" for ln in sig_lines
    )
```

- [ ] **Step 5: Verify the ffuf e2e**

```bash
.venv/bin/python -m pytest tests/runners/test_ffuf_scan_e2e.py -v
```

Expected: 1 skipped on hosts without ffuf; 1 passed on the VPS.

- [ ] **Step 6: Run the full suite + lint**

```bash
make smoke
```

Expected: ruff + mypy clean, every prior test still passing, all new tests passing. Approximate counts: 168 from 3b + 9 (hashing — +4 katana + 5 ffuf) + 11 (katana tool) + 7 (katana runner) + 11 (ffuf tool) + 7 (ffuf runner) + 9 (classify) + 1 katana e2e (skipped without binary) + 1 ffuf e2e (skipped without binary) ≈ **223 passing / 2 skipped** on a typical dev host.

- [ ] **Step 7: Commit**

```bash
git add tests/runners/test_katana_scan_e2e.py \
        tests/runners/test_ffuf_scan_e2e.py \
        tests/fixtures/ffuf_wordlists/tiny.txt
git commit -m "test: end-to-end katana + ffuf smoke against mock target"
```

---

## Self-review

### Spec coverage

| Spec item | Where covered |
| --- | --- |
| Section 3 — Shared Active Runner Contract: gate order, prereq freshness | Task 3 (katana_scan `_recent_httpx_success`), Task 6 (ffuf_scan `_recent_httpx_success`) |
| Section 3 — Per-request scope enforcement: katana post-tool re-filter via `scope.is_in_scope` | Task 3 (`run_program` dual-key filter), Task 3 Step 7 (OOS-target dual-key tests) |
| Section 3 — Per-request scope enforcement: ffuf no `-r` follow-redirects, post-tool re-filter | Task 5 (`build_command` omits `-r`; test asserts), Task 6 (dual-key filter), Task 6 Step 7 (dual-key tests) |
| Section 3 — Shared Artifact Contract: 5 required files per run | Task 3 + 6 (`_write_signals_jsonl`, `_write_required_artifacts`, `_write_manifest`); happy-path tests assert all 5 exist; prereq-missing tests assert all 5 exist for `status='skipped'` |
| Section 3.3 — katana caps (depth, duration, max_urls) + safety flags | Task 2 (`MAX_DEPTH`, `MAX_DURATION_S`, `MAX_URLS`, `UnsafeCrawlProfile`); locked constants test; reject-excessive tests for all three caps |
| Section 3.3 — katana runner reads from httpx live roots, normalized endpoint signals | Task 3 (`_load_in_scope_service_urls`); happy-path test asserts `signal_type='endpoint_discovered'` |
| Section 3.4 — ffuf wordlist allowlist + request caps + auto-calibration | Task 5 (`APPROVED_WORDLISTS`, `UnsafeWordlistProfile`, `-mc`/`-fc`/`-ac`/`-t`/`-rate`/`-timeout` flags); locked constants test; reject-non-approved test; reject-missing-file test |
| Section 3.4 — ffuf normalized discovery signals | Task 5 (`parse_json` emits `signal_type='content_match'`); Task 6 (runner records them) |
| Section 4 — Signature composition for katana (`<path>|<sorted_params>|<METHOD>`) | Task 1 (`signature_for_katana`); 4 unit tests including path-only fallback |
| Section 4 — Signature composition for ffuf (`<path>|<status>|<length_bucket>|<content_type>`) | Task 1 (`signature_for_ffuf` + `_length_bucket` + `_normalize_content_type`); 5 unit tests covering all 5 buckets and CT normalization |
| Section 4 — Finding hash composition reuses normalized asset/target | Task 2 (`_to_signal` calls `hashing.normalize_asset` + `hashing.normalize_target`); Task 5 (ditto for `_result_to_signal`) |
| Section 5 — katana every 2 days at 03:15 UTC, ffuf weekly Sun 04:20 UTC | Documented in spec section 5; timer unit files are Phase 3d's deliverable. Phase 3c ships the CLI commands the timer units invoke. |
| Section 6.3c — Triage adapters for katana and ffuf signals | Task 7 (classify dispatch table extensions); 6 new classify tests |
| Section 7 — Prereq freshness against httpx (24h window) | Task 3 + 6 (`_recent_httpx_success` mirrors nuclei_scan); prereq-missing tests for both runners |
| Section 7 — Signals atomic boundary (DB row authoritative; JSONL write-then-reconcile) | Task 3 + 6 (`signals.insert_signals` is called before `_write_signals_jsonl`); manifest documents the artifact schema. Reconcile-from-DB logic is deferred to 3d hardening per the 3b plan. |

### Items deferred from 3c (intentional)

- **systemd timer unit files** for `katana-crawl.timer` and `ffuf-scan.timer`. Phase 3d ships timer units in `ops/systemd/`; Phase 3c ships only the CLI commands the timer services invoke.
- **Triage cross-tool correlation** (e.g. boosting confidence when katana finds `/admin` AND ffuf finds `/admin` on the same host). The dispatch in Task 7 handles each signal independently; smarter correlation is a future hardening item that would live in `triage/engine.py` rather than `triage/classify.py`.
- **Wordlist provisioning automation** (downloading SecLists onto the VPS, validating SHA-256s). The runner reads `WORDLISTS_DIR` from env and validates the file exists at scan time — provisioning the directory is an ops task, documented in the operator runbook (Phase 3d) rather than enforced by the runner.
- **katana scope regex (`-fs` / `-cs`)** derived from `scope.in_scope` / `scope.out_of_scope` glob patterns. The post-tool re-filter (dual-key OOS check on every emitted signal) is the authoritative scope enforcement; runtime experience may motivate adding a regex hint in a follow-up.
- **Daily-digest consumption of new katana/ffuf findings**. Phase 3d.

### Placeholder scan

Grep the plan for `TBD`, `TODO`, `pseudocode`, `[fill in]`, `[example]`, `XXX`, `FIXME`. Expected: zero matches. Every code block contains real Python or shell or JSON; every command shows a literal command line; every "expected" assertion describes the actual output the runner produces.

### Type consistency

- `Signal` (Phase 3a) — re-used in Tasks 2, 3, 5, 6, 7, 9. Schema is the existing `signals` table; no changes.
- `HttpService` (Phase 3a) — re-used in Task 3 + 6 tests via `_seed_httpx_run_and_services`. No changes.
- `ActiveRunResult` (Phase 3a) — returned unchanged by `katana_scan.run_program` and `ffuf_scan.run_program`. Same 8 fields.
- `ToolRunResult` (Phase 3a, frozen dataclass) — re-used by both runners. `outputs` field accepts `tuple[Signal, ...]`; `raw_stdout` / `raw_stderr` / `terminated_reason` / `aborted` / `source_failures` / `timed_out` all used by the new CLI wiring.
- `UnsafeCrawlProfile` (Task 2) — new exception, never crosses module boundaries except in `katana_scan_cli.main()`.
- `UnsafeWordlistProfile` (Task 5) — new exception, raised inside `ffuf_tool.build_command` and inside `ffuf_scan_cli._resolve_wordlist_path`; caught only by `ffuf_scan_cli.main()`.
- `Classification` (Phase 3b, `classify.py`) — extended via two new dispatch branches, no signature change. Existing callers (`engine._process_signal`) are unaffected.

### Plan-policy compliance

- **File-size cap**: every new source file is under the 200-line cap. The closest calls are `katana_scan.py` (~190 lines), `katana_scan_cli.py` (~120 lines), `ffuf_scan.py` (~195 lines), `ffuf_scan_cli.py` (~190 lines). The CLI/runner split mirrors `nuclei_scan` / `nuclei_scan_cli`.
- **TDD discipline**: every task writes the failing test FIRST, runs it to confirm RED, then minimal impl, then GREEN, then commits. No exceptions.
- **Conventional Commits**: every commit message uses `feat:` / `test:` / `chore:` per CONTRIBUTING.md.
- **No new runtime dependencies**: both parsers use stdlib `json` and `urllib.parse`. The `idna` decision from Phase 3b stands (stdlib).
- **Safety boundaries are non-negotiable**:
  - katana caps: `MAX_DEPTH=2`, `MAX_DURATION_S=600`, `MAX_URLS=5000` — locked-constants test prevents drift.
  - ffuf wordlists: `APPROVED_WORDLISTS = frozenset({"common.txt", "raft-medium-directories.txt"})` — locked-constants test prevents drift.
  - Both runners refuse to invoke their tools with unsafe profiles via typed exceptions (`UnsafeCrawlProfile`, `UnsafeWordlistProfile`).
- **No mocked findings**: the e2e tests run real binaries against the in-repo mock target, not against any real program.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-12-phase-3c-katana-ffuf.md`. Two execution options:

1. **Subagent-Driven** (recommended) — a fresh subagent per task. Tasks 1, 2, 5, 7 have no inter-task dependencies and can run in parallel. Tasks 3, 6 depend on Tasks 2, 5 respectively. Task 4 depends on Task 3. Task 8 depends on Task 6. Task 9 depends on Tasks 3 + 6. Review between tasks; pay extra attention to the OOS dual-key filter (3 + 6) and the wordlist allowlist (5) — those are the load-bearing safety invariants.

2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints between Tasks 2 / 5 / 6 / 9.

Which approach?
