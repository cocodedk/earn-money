# Juice Shop Engine Integration — Design Decisions

> Target: `target.cocode.dk` (operator-owned OWASP Juice Shop, 112 challenges, 47 solved).
> Engine: `h1.cocode.dk` (earn-money bug-bounty automation pipeline).
> Goal: the engine autonomously solves Juice Shop exercises via existing
> runners + targeted extensions. Full coverage of all 112 is aspirational;
> see challenge-family matrix below for realistic scope.

---

## Decision 1 — scope-sync for non-HackerOne platforms

**Problem.** `scope-sync` is HackerOne-only. Its broad exception handler
freezes any program it cannot sync. Registering `programs/local/juice-shop/`
before this fix would freeze the program on first cron.

**Decision: scope-sync exits-0 for unknown platforms, before any other logic.**

The guard is the **very first thing in `main()`**, before `RECON_ENABLED`
check, before `hackerone.Client()` construction, before any exception handler.
Implementation:

```python
def main(argv: list[str] | None = None) -> int:
    args = parser.parse_args(argv)
    if args.platform != "hackerone":
        print(f"scope-sync: platform {args.platform!r} has no sync adapter — skipping")
        return 0
    # ... rest of existing logic unchanged
```

A dedicated regression test verifies `main(["--platform", "local", "--program", "juice-shop"])` returns 0 and writes no FROZEN flag.

**Files changed:** `src/earn_money/runners/scope_sync.py`,
`tests/runners/test_scope_sync.py`.

---

## Decision 2 — nuclei template expansion for owned targets

**Problem.** Approved set is conservative. For `target.cocode.dk` we want
broader coverage without weakening production safety.

**Decision: `roe.md` gains `extra_nuclei_dirs`, backed by a typed `roe.py`
parser and a locked `EXTRA_ALLOWED_DIRS` constant.**

New file `src/earn_money/roe.py`:

```python
from __future__ import annotations
import yaml
from pathlib import Path
from earn_money.config import Paths

def load_extra_nuclei_dirs(paths: Paths, platform: str, slug: str) -> list[str]:
    """Return extra_nuclei_dirs from roe.md, or [] if absent/unset."""
    roe_path = paths.programs / platform / slug / "roe.md"
    if not roe_path.exists():
        return []
    front = _parse_frontmatter(roe_path)
    dirs = front.get("extra_nuclei_dirs") or []
    if not isinstance(dirs, list):
        raise ValueError(f"extra_nuclei_dirs must be a list in {roe_path}")
    return [str(d) for d in dirs]

def _parse_frontmatter(path: Path) -> dict:
    text = path.read_text()
    if not text.startswith("---"):
        return {}
    end = text.index("---", 3)
    return yaml.safe_load(text[3:end]) or {}
```

`nuclei_tool.build_command()` accepts a new `extra_dirs: Sequence[str] = ()`
parameter. Each entry is validated against `EXTRA_ALLOWED_DIRS`; if any entry
is not in the set, `UnsafeTemplateProfile` is raised (not silently skipped).

`nuclei_scan_cli._build_real_tool()` loads extra dirs via `roe.load_extra_nuclei_dirs()`
and passes them to the tool. Tests prove extra dirs reach `build_command()`.

`EXTRA_ALLOWED_DIRS` initial value (assertion-locked same as `APPROVED_TEMPLATE_DIRS`):
```
http/vulnerabilities
http/injection
http/xss
```

`roe.md` for `local/juice-shop`:
```yaml
extra_nuclei_dirs:
  - http/vulnerabilities
  - http/injection
  - http/xss
```

**Files changed / created:** `src/earn_money/roe.py`, `src/earn_money/recon/nuclei_tool.py`,
`src/earn_money/runners/nuclei_scan.py`, `src/earn_money/runners/nuclei_scan_cli.py`,
`tests/recon/test_nuclei_tool.py`, `tests/runners/test_nuclei_scan.py`.

---

## Decision 3 — Juice Shop challenge solver

**Problem.** Existing pipeline covers ~5-15 of 112 challenges.

**Realistic coverage by family (challenge-family matrix):**

| Family | Count | Engine approach | Expected coverage |
|---|---|---|---|
| Sensitive Data Exposure | 16 | nuclei exposures + sourcemap + katana | ~8 |
| Injection (SQLi) | 13 | `sqli-probe` (new) | ~6 |
| XSS | 9 | `xss-probe` (new) | ~4 |
| Broken Access Control | 12 | `auth-bypass-probe` (new) | ~4 |
| Broken Authentication | 9 | `auth-bypass-probe` (new) | ~3 |
| Vulnerable Components | 8 | nuclei cves | ~4 |
| Miscellaneous / Config | 6 | nuclei misconfiguration | ~3 |
| Improper Input Validation | 12 | sqli+xss probes | ~3 |
| Security Misconfiguration | 4 | nuclei | ~2 |
| Broken Anti Automation | 4 | out of scope for engine | 0 |
| Insecure Deserialization | 3 | out of scope for engine | 0 |
| Cryptographic Issues | 5 | out of scope for engine | 0 |
| Observability Failures | 4 | nuclei exposed-panels | ~2 |
| XSS (CSP/HTTPheader) | 4 | `xss-probe` | ~1 |
| XXE | 2 | nuclei | ~1 |
| Unvalidated Redirects | 2 | nuclei | ~1 |
| Web3 / Blockchain / Stego | ~6 | out of scope for engine | 0 |

**Realistic engine ceiling: ~40-45 solved** (from 47 current → ~85-90 total).
"All challenges" includes Blockchain Hype, Memory Bomb, etc. that require
browser automation or non-HTTP techniques — the engine ceiling is documented,
not hidden.

**Decision: build generic web-exploit primitives (option B).**

Three new runners, gated by explicit RoE flags:

### Probe input contract

Probes read from `discovered_urls.jsonl` artifact files written by the
katana-crawl runner (one file per run at
`recon/outputs/<platform>/<slug>/katana/<date>/<run_id>/discovered_urls.jsonl`).
The JSONL schema is `{"url": str, "method": str}` per `DiscoveredUrl`.
Probes locate the most recent katana artifact via the `recon_runs` DB table
(tool=`katana`, status=`success`, sorted by `finished_at` desc). If no
recent katana run exists (freshness window: 24h), the probe records a
`prereq_missing` signal and exits cleanly — same pattern as nuclei's
existing prereq check.

**Katana scope enforcement**: katana is invoked with `-cs <host>` where the
host list comes from **`http_services.subdomain`** — the already-httpx-validated,
in-scope live hosts — NOT from raw `scope.in_scope` patterns. This is exact:
no wildcard expansion, no apex fallback, no OOS request before the filter.
`katana_tool.build_command()` gains a `crawl_scope: Sequence[str] = ()` parameter.
`katana_crawl.py` passes `[svc.subdomain for svc in in_scope_services]` to it.
The existing `filter_in_scope()` second-pass remains. New probes make GET
requests only to URLs from the katana artifact (pre-filtered).

**Files changed for katana scope fix:**
- `src/earn_money/recon/katana_tool.py` — add `crawl_scope` param to `build_command()`
- `src/earn_money/runners/katana_crawl.py` — pass `http_services` hosts as crawl scope
- `src/earn_money/runners/katana_crawl_cli.py` — no changes needed (factory only)
- `tests/recon/test_katana_tool.py` — assert `-cs` flags appear in built command

**GET-only rule**: probes NEVER replay recorded POST bodies. GET-with-params
is the only automated probe vector. POST-based injection (form submissions,
REST bodies) requires `mutation_testing_authorized: true` in `roe.md` and is
out of scope for the initial build.

### `sqli-probe`
- Input: GET URLs with query parameters from the most recent katana artifact.
- Payloads: error-based (`'`), boolean-based (`' OR '1'='1`). Time-based
  (`SLEEP(2)`) is opt-in via `roe.md: sqli_time_based: true` — off by default
  because timing probes add latency and can look like DoS to WAFs.
- Detection: response body contains SQL error strings OR boolean-response
  differs (length delta > 20% between true/false probe).
- RoE gate: `policy = rate-limited-OK`. No `destructive_payloads_authorized`
  required (GET-only, no state change).
- Signal: `sqli_candidate`.

### `xss-probe`
- Input: GET URLs with query parameters from katana artifact.
- Markers: non-executing unique string (`xss-mrk-{uuid}`) injected into each
  parameter; flag if marker appears verbatim in response body (reflected).
  Never `<script>`, never event handlers.
- RoE gate: `policy = rate-limited-OK`.
- Signal: `xss_candidate`.

### `auth-bypass-probe`
- Sub-tests: (a) known admin paths (`/admin`, `/#/administration`) — the probe
  makes a GET with no auth headers AND a GET with the extracted admin JWT
  (obtained by logging in with `authorized_test_accounts[0]` if present);
  a path is `auth_bypass_candidate` only if unauthenticated GET returns the
  same response body hash as the authenticated GET on a path that returns
  non-trivial content (status 200 + body length > 500 bytes),
  (b) JWT alg:none — the probe makes its own authenticated GET to the target
  (using `authorized_test_accounts[0]` login response) to extract the JWT
  from response headers/cookies, then strips the signature and re-submits;
  flag if the modified JWT is accepted (response status differs from 401),
  (c) default credentials — **only against explicitly named accounts in
  `roe.md: authorized_test_accounts`**, with a **lockout budget of 3 attempts
  per account per run** (configurable via `roe.md: auth_lockout_budget: 3`).
  No credential testing against accounts not in the allowlist.
- RoE gate: sub-test (c) requires `auth_testing_authorized: true` in `roe.md`.
- Signal: `auth_bypass_candidate`.

### Typed RoE fields added (in `roe.py`)

```python
@dataclass
class RoE:
    extra_nuclei_dirs: list[str] = field(default_factory=list)
    auth_testing_authorized: bool = False
    sqli_time_based: bool = False
    mutation_testing_authorized: bool = False
    auth_lockout_budget: int = 3
    # existing fields unchanged
```

`roe.py` validates each field type on load; invalid types raise `ValueError`.

### `juiceshop_adapter.py` — score model (not a runner)
Polls `GET /api/Challenges` before and after each pipeline run.
Records `(challenge_name, category, difficulty, solved_before, solved_after)`
in a `juice_shop_scores` table per run. Output: markdown report at
`benchmarks/scores/local-juice-shop.md` showing delta of newly solved
challenges per run. This is a separate model from `benchmark-score` (which
scores FN coverage against disclosure corpus) — the two are independent.

**Wiring**: a new `bin/juice-shop-run` CLI wraps the full workflow:
```
bin/juice-shop-run:
  1. Record pre-run solved challenges via GET /api/Challenges → juiceshop_adapter.snapshot_pre()
  2. exec bin/passive-recon --platform local --program juice-shop   # seeds assets table
  3. exec bin/active-tick --platform local --program juice-shop
  4. Record post-run solved challenges → juiceshop_adapter.snapshot_post()
  5. Write benchmarks/scores/local-juice-shop.md
```
Step 2 is required because `httpx_probe` loads targets only from the
`assets` DB table (not from `scope.md` directly). Without a prior
passive-recon pass, the assets table is empty and all active runners
see 0 targets. `passive-recon` for `local/juice-shop` resolves
`target.cocode.dk` via DNS and inserts it into `assets` with
`in_scope_at_observation=1`.

`active-tick` is unchanged — the adapter wraps it externally.

**Files changed / created:**
- `src/earn_money/roe.py` (already in Decision 2)
- `src/earn_money/recon/sqli_tool.py`, `xss_tool.py`, `auth_bypass_tool.py`
- `src/earn_money/runners/sqli_probe.py`, `sqli_probe_cli.py`
- `src/earn_money/runners/xss_probe.py`, `xss_probe_cli.py`
- `src/earn_money/runners/auth_bypass_probe.py`, `auth_bypass_probe_cli.py`
- `src/earn_money/triage/juiceshop_adapter.py`
- `src/earn_money/db.py` (migration for `juice_shop_scores`)
- `src/earn_money/engine/active_pipeline.py` (register new runners)
- `src/earn_money/engine/active_tick_cli.py` (wire tool factories)
- Tests for each new tool and runner.

---

## Execution order

> **Step 1 (scope-sync fix) MUST land before step 2 (program registration)**
> to avoid freezing the program on first cron.

1. Fix scope-sync platform guard (code + tests).
2. Fix passive-recon platform guard (remove hackerone restriction).
3. Fix katana `-cs`: add `crawl_scope` to `katana_tool.build_command()`, pass `http_services` hosts in `katana_crawl.py`, add tests to `test_katana_tool.py`.
4. Register `programs/local/juice-shop/` (scope.md + roe.md).
5. Run existing pipeline — baseline: httpx → nuclei (standard) + katana + sourcemap.
6. Add `roe.py` + `extra_nuclei_dirs` support to nuclei_tool + nuclei_scan_cli.
5. Run pipeline with expanded nuclei — second baseline.
6. Build `sqli-probe` (TDD).
7. Build `xss-probe` (TDD).
8. Build `auth-bypass-probe` (TDD).
9. Wire new runners into `active_pipeline.py`.
10. Build `juiceshop_adapter.py` + migration.
11. Full pipeline run.

**Acceptance criteria (exit criteria):**
- `pytest` green (all existing + new tests).
- `bin/active-tick --platform local --program juice-shop` exits 0.
- `benchmarks/scores/local-juice-shop.md` exists and shows:
  - **≥ 85 total solved** (engine solves ≥ 38 new challenges atop the current 47), OR
  - engine solves ≥ 40 challenges not previously solved (delta basis).
- No OOS drops (engine only touches `target.cocode.dk`).
- `programs/local/juice-shop/FROZEN` does NOT exist.

---

## Decisions log

**Round 6 cursor-agent issues addressed:**

1. `bin/juice-shop-run` now runs `passive-recon` before `active-tick` to seed the `assets` table. Without this, httpx_probe sees 0 targets and all subsequent runners skip.

**Round 5 cursor-agent issues addressed:**

1. Katana `-cs` now derives from `http_services.subdomain` (already-validated live hosts), not from raw `scope.in_scope` patterns. Code changes for `katana_tool.py`, `katana_crawl.py`, `test_katana_tool.py` added to files list and execution order.

**Round 4 cursor-agent issues addressed:**

1. Katana `-cs` uses explicit in-scope hosts (not apex domain) to prevent crawling `*.cocode.dk` before filter runs.
2. Stale Round 1 Decisions log entry corrected: input is katana JSONL artifact, not signals table.

**Round 3 cursor-agent issues addressed:**

1. Katana scope enforcement: `-cs <apex>` crawl-scope flag added to katana invocation; probe GET requests limited to URLs in katana artifact (no independent link-following).
2. JWT alg:none: probe makes its own authenticated GET to extract JWT from response; not from katana artifacts.
3. `juiceshop_adapter.py` wiring: `bin/juice-shop-run` CLI wraps pre-snapshot + active-tick + post-snapshot; adapter decoupled from active-tick.
4. Admin-path auth bypass: defined as unauthenticated-GET matching authenticated-GET body on non-trivial (>500B) admin-only content — not just any 200.

**Round 2 cursor-agent issues addressed:**

1. Acceptance criteria strengthened: `≥85 total solved` OR `≥40 newly solved`.
2. Probe input contract: probes read from katana's `discovered_urls.jsonl` artifact; GET-only rule documented; POST replay explicitly prohibited without `mutation_testing_authorized`.
3. Typed `RoE` dataclass added with all new fields; validation on load.
4. POST replay safety: GET-only probe rule + `mutation_testing_authorized` gate.

**Round 1 cursor-agent issues addressed:**

1. scope-sync guard now explicitly first-in-main, before all other logic.
2. `roe.py` added to Decision 2 file list with full implementation sketch.
3. `nuclei_scan_cli.py` added to Decision 2 file list.
4. Challenge-family matrix added; ceiling ~85-90 total, not all-112; out-of-scope families documented.
5. Input corpus for probes: katana `discovered_urls.jsonl` artifact (GET URLs with query params); not the signals table.
6. Credential testing now gated on `authorized_test_accounts` + `auth_testing_authorized: true` + lockout budget.
7. SQLi/XSS classified as read-only; state-changing payloads never sent; `sqli_time_based` is separate opt-in.
8. `juiceshop_adapter.py` now polls `/api/Challenges` before/after (solved-state model), separate from benchmark-score.
9. Execution order swapped: scope-sync fix first, program registration second.
10. Acceptance criteria with numeric exit conditions defined.
