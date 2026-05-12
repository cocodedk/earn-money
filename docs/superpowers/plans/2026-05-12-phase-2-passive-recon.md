# Phase 2 — Passive Recon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first recon runner. After Phase 2, the operator can run `bin/passive-recon --program <slug>` and have the system pull subdomains from passive sources (subfinder + Chaos), resolve them, and upsert the resulting assets into the per-program SQLite store from Phase 1. Active probing and the daily digest are out of scope — those land in Phase 3.

**Architecture:** Same module conventions as Phase 1. Each unit has one responsibility, tests mirror the source layout, no network calls in tests. External CLI tools (`subfinder`) are invoked through a thin subprocess wrapper that is mocked in tests. The Chaos API client follows the same pattern as `platforms.hackerone` (httpx + MockTransport). DNS resolution uses `dnspython` against a configurable resolver so we can swap to a self-hosted resolver in production without code changes.

**Tech Stack:** Python 3.12, stdlib `subprocess` (for subfinder), `httpx` (Chaos API), `dnspython` (DNS), SQLite (per-program store from Phase 1), `pytest`, `pytest-mock`, `ruff`, `mypy`. System-installed binaries on the VPS: `subfinder` (Project Discovery). The dev box does NOT need `subfinder` — tests mock its output.

---

## Prerequisites (operator, one-time)

These are operator actions. The pipeline can't run for real until they're done.

- `subfinder` installed on the VPS that runs the cron. Install via `go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest` or download a release binary. Verify with `subfinder -version`. Tests do not require this.
- A Chaos API token from <https://chaos.projectdiscovery.io>. Free tier is sufficient for Phase 2. Add it to the same `.env` used in Phase 1:

  ```bash
  CHAOS_API_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  ```

- The program being recon'd must already be onboarded per `programs/README.md` (i.e., `scope.md` exists with a `policy:` tier set, and a successful `bin/scope-sync` has populated the in-scope list).
- `RECON_ENABLED` flag file present at the repo root.

---

## File structure

This plan creates and modifies these files. Subsequent tasks reference them by exact path.

**Created:**

```
earn-money/
├── src/
│   └── earn_money/
│       ├── policy.py
│       └── recon/
│           ├── __init__.py
│           ├── subfinder.py
│           ├── chaos.py
│           ├── resolver.py
│           └── assets.py
├── src/earn_money/runners/passive_recon.py
├── tests/
│   ├── test_policy.py
│   ├── recon/
│   │   ├── __init__.py
│   │   ├── test_subfinder.py
│   │   ├── test_chaos.py
│   │   ├── test_resolver.py
│   │   └── test_assets.py
│   ├── runners/test_passive_recon.py
│   └── fixtures/
│       ├── subfinder_output.txt
│       └── chaos_subdomains.json
└── bin/passive-recon
```

**Modified:**

- `pyproject.toml` — add `dnspython>=2.6` to runtime dependencies.
- `programs/README.md` — append a "Passive recon" section.

---

## Task 1 — Policy enforcement helper

**Files:**
- Create: `src/earn_money/policy.py`
- Create: `tests/test_policy.py`

The runner must refuse to start against a `manual-only` program and must restrict an `ambiguous` program to passive operations. The helper takes a `Scope` and a `Mode` and raises `PolicyViolation` when the requested operation is not permitted.

**Mode rules** (from the design spec):

| `scope.policy` | `mode="passive"` (subdomain enumeration, DNS, API queries) | `mode="active"` (HTTP probing, content discovery, etc.) |
|---|---|---|
| `rate-limited-OK` | allowed | allowed |
| `ambiguous` | allowed | refused |
| `manual-only` | refused | refused |

- [ ] **Step 1.1 — Write the failing tests at `tests/test_policy.py`**

```python
from __future__ import annotations

import pytest

from earn_money import policy, scope


def _scope(p: scope.Policy) -> scope.Scope:
    return scope.Scope(
        platform="hackerone", slug="example", policy=p,
        in_scope=[], out_of_scope=[], notes="",
        scope_hash="", last_synced="",
    )


def test_rate_limited_allows_both_modes() -> None:
    s = _scope("rate-limited-OK")
    policy.require_policy_allows(s, mode="passive")
    policy.require_policy_allows(s, mode="active")


def test_ambiguous_allows_passive_refuses_active() -> None:
    s = _scope("ambiguous")
    policy.require_policy_allows(s, mode="passive")
    with pytest.raises(policy.PolicyViolation):
        policy.require_policy_allows(s, mode="active")


def test_manual_only_refuses_both() -> None:
    s = _scope("manual-only")
    with pytest.raises(policy.PolicyViolation):
        policy.require_policy_allows(s, mode="passive")
    with pytest.raises(policy.PolicyViolation):
        policy.require_policy_allows(s, mode="active")


def test_violation_message_names_policy_and_mode() -> None:
    s = _scope("manual-only")
    with pytest.raises(policy.PolicyViolation) as excinfo:
        policy.require_policy_allows(s, mode="passive")
    assert "manual-only" in str(excinfo.value)
    assert "passive" in str(excinfo.value)
```

- [ ] **Step 1.2 — Run tests to verify they fail**

Run: `make test`
Expected: ImportError — `policy` module does not exist.

- [ ] **Step 1.3 — Write `src/earn_money/policy.py`**

```python
"""Policy-tier enforcement for recon runners."""

from __future__ import annotations

from typing import Literal

from earn_money.scope import Scope

Mode = Literal["passive", "active"]


class PolicyViolation(Exception):
    """Raised when the requested mode is not permitted by the program's policy."""


def require_policy_allows(scope: Scope, *, mode: Mode) -> None:
    if scope.policy == "rate-limited-OK":
        return
    if scope.policy == "ambiguous" and mode == "passive":
        return
    raise PolicyViolation(
        f"Program {scope.platform}/{scope.slug} has policy={scope.policy!r}; "
        f"mode={mode!r} is not permitted. "
        "Operator must scan this program manually or escalate scope tier."
    )
```

- [ ] **Step 1.4 — Run tests to verify they pass**

Run: `make test`
Expected: all 4 policy tests pass.

- [ ] **Step 1.5 — Commit**

```bash
git add src/earn_money/policy.py tests/test_policy.py
git commit -m "feat: add PolicyViolation guard for recon runners"
```

---

## Task 2 — Subfinder subprocess wrapper

**Files:**
- Create: `src/earn_money/recon/__init__.py`
- Create: `src/earn_money/recon/subfinder.py`
- Create: `tests/recon/__init__.py`
- Create: `tests/recon/test_subfinder.py`
- Create: `tests/fixtures/subfinder_output.txt`

A thin wrapper around `subfinder -d <domain> -silent -all`. The wrapper runs the subprocess, captures stdout, and returns a deduplicated list of subdomains. Tests mock the subprocess via `subprocess.run` patching — they never actually execute `subfinder`.

- [ ] **Step 2.1 — Create the package init files**

`src/earn_money/recon/__init__.py`:
```python
"""Recon — passive and active discovery."""
```

`tests/recon/__init__.py`: empty file (zero bytes).

- [ ] **Step 2.2 — Write the fixture at `tests/fixtures/subfinder_output.txt`**

```
api.example.com
www.example.com
api.example.com
mail.example.com
internal.example.com
```

(Note the duplicate `api.example.com` — the wrapper must dedupe.)

- [ ] **Step 2.3 — Write the failing tests at `tests/recon/test_subfinder.py`**

```python
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from earn_money.recon import subfinder


def test_runs_subfinder_with_expected_args(
    fixtures_dir: Path, mocker: pytest.MonkeyPatch
) -> None:
    output = (fixtures_dir / "subfinder_output.txt").read_text(encoding="utf-8")
    mock_run = mocker.patch(
        "earn_money.recon.subfinder.subprocess.run",
        return_value=MagicMock(stdout=output, returncode=0, stderr=""),
    )

    result = subfinder.enumerate_subdomains("example.com")

    assert sorted(result) == [
        "api.example.com",
        "internal.example.com",
        "mail.example.com",
        "www.example.com",
    ]
    args, kwargs = mock_run.call_args
    assert args[0] == ["subfinder", "-d", "example.com", "-silent", "-all"]
    assert kwargs["check"] is True
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


def test_returns_empty_list_on_no_output(mocker: pytest.MonkeyPatch) -> None:
    mocker.patch(
        "earn_money.recon.subfinder.subprocess.run",
        return_value=MagicMock(stdout="", returncode=0, stderr=""),
    )
    assert subfinder.enumerate_subdomains("example.com") == []


def test_subprocess_failure_raises(mocker: pytest.MonkeyPatch) -> None:
    mocker.patch(
        "earn_money.recon.subfinder.subprocess.run",
        side_effect=subprocess.CalledProcessError(
            returncode=1, cmd="subfinder", stderr="boom"
        ),
    )
    with pytest.raises(subfinder.SubfinderError):
        subfinder.enumerate_subdomains("example.com")


def test_missing_binary_raises(mocker: pytest.MonkeyPatch) -> None:
    mocker.patch(
        "earn_money.recon.subfinder.subprocess.run",
        side_effect=FileNotFoundError("subfinder"),
    )
    with pytest.raises(subfinder.SubfinderError):
        subfinder.enumerate_subdomains("example.com")
```

- [ ] **Step 2.4 — Run tests to verify they fail**

Run: `make test`
Expected: ImportError — `recon.subfinder` does not exist.

- [ ] **Step 2.5 — Write `src/earn_money/recon/subfinder.py`**

```python
"""Subfinder subprocess wrapper. Passive subdomain enumeration."""

from __future__ import annotations

import subprocess


class SubfinderError(Exception):
    """Raised when subfinder is missing or exits non-zero."""


def enumerate_subdomains(domain: str) -> list[str]:
    """Return a deduplicated list of subdomains for ``domain``.

    Calls ``subfinder -d <domain> -silent -all``. Requires subfinder to be on
    PATH. Raises ``SubfinderError`` when the binary is missing or exits
    non-zero.
    """
    try:
        result = subprocess.run(
            ["subfinder", "-d", domain, "-silent", "-all"],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SubfinderError(
            "subfinder binary not found on PATH. Install per "
            "https://github.com/projectdiscovery/subfinder."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SubfinderError(
            f"subfinder exited {exc.returncode}: {exc.stderr.strip()}"
        ) from exc

    seen: set[str] = set()
    out: list[str] = []
    for line in result.stdout.splitlines():
        sub = line.strip().lower()
        if sub and sub not in seen:
            seen.add(sub)
            out.append(sub)
    return out
```

- [ ] **Step 2.6 — Run tests to verify they pass**

Run: `make test`
Expected: 4 subfinder tests pass.

- [ ] **Step 2.7 — Commit**

```bash
git add src/earn_money/recon/__init__.py src/earn_money/recon/subfinder.py tests/recon/__init__.py tests/recon/test_subfinder.py tests/fixtures/subfinder_output.txt
git commit -m "feat: add subfinder subprocess wrapper"
```

---

## Task 3 — Chaos API client

**Files:**
- Create: `src/earn_money/recon/chaos.py`
- Create: `tests/recon/test_chaos.py`
- Create: `tests/fixtures/chaos_subdomains.json`

Calls the Chaos public DNS dataset (`https://dns.projectdiscovery.io/dns/<domain>/subdomains`) with the `Authorization: <token>` header. Same pattern as `platforms.hackerone`: httpx + MockTransport in tests.

- [ ] **Step 3.1 — Write the fixture at `tests/fixtures/chaos_subdomains.json`**

```json
{
  "domain": "example.com",
  "subdomains": ["api", "api", "auth", "stage", "WWW"]
}
```

(Chaos sometimes returns duplicates and mixed casing — the client must dedupe and normalize.)

- [ ] **Step 3.2 — Write the failing tests at `tests/recon/test_chaos.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from earn_money.recon import chaos


def test_fetch_returns_normalized_fqdns(fixtures_dir: Path) -> None:
    payload = json.loads((fixtures_dir / "chaos_subdomains.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "dns.projectdiscovery.io"
        assert request.url.path == "/dns/example.com/subdomains"
        assert request.headers["authorization"] == "tkn"
        return httpx.Response(200, json=payload)

    client = chaos.Client(token="tkn", transport=httpx.MockTransport(handler))
    result = client.fetch_subdomains("example.com")

    assert sorted(result) == [
        "api.example.com",
        "auth.example.com",
        "stage.example.com",
        "www.example.com",
    ]


def test_fetch_raises_on_non_200() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "unauthorized"})

    client = chaos.Client(token="tkn", transport=httpx.MockTransport(handler))
    with pytest.raises(chaos.ChaosAPIError):
        client.fetch_subdomains("example.com")


def test_missing_token_raises() -> None:
    with pytest.raises(chaos.ChaosAPIError):
        chaos.Client(token="")


def test_fetch_handles_empty_response() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"domain": "example.com", "subdomains": []})

    client = chaos.Client(token="tkn", transport=httpx.MockTransport(handler))
    assert client.fetch_subdomains("example.com") == []


def test_client_supports_context_manager() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"domain": "example.com", "subdomains": []})

    with chaos.Client(token="tkn", transport=httpx.MockTransport(handler)) as client:
        assert client.fetch_subdomains("example.com") == []
```

- [ ] **Step 3.3 — Run tests to verify they fail**

Run: `make test`
Expected: ImportError — `recon.chaos` does not exist.

- [ ] **Step 3.4 — Write `src/earn_money/recon/chaos.py`**

```python
"""Chaos public DNS API client."""

from __future__ import annotations

import httpx

_BASE_URL = "https://dns.projectdiscovery.io"


class ChaosAPIError(Exception):
    """Raised on HTTP failure or missing credentials."""


class Client:
    def __init__(
        self,
        *,
        token: str,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 20.0,
    ) -> None:
        if not token:
            raise ChaosAPIError(
                "Chaos credentials missing — set CHAOS_API_TOKEN."
            )
        self._client = httpx.Client(
            base_url=_BASE_URL,
            headers={"Authorization": token, "Accept": "application/json"},
            transport=transport,
            timeout=timeout,
        )

    def fetch_subdomains(self, domain: str) -> list[str]:
        """Return Chaos-known FQDNs for ``domain``. Deduped and lowercased."""
        try:
            response = self._client.get(f"/dns/{domain}/subdomains")
        except httpx.RequestError as exc:
            raise ChaosAPIError(
                f"Network error fetching {domain}: {exc}"
            ) from exc
        if response.status_code != 200:
            raise ChaosAPIError(
                f"Chaos API returned {response.status_code} for {domain}: "
                f"{response.text}"
            )
        data = response.json()
        seen: set[str] = set()
        out: list[str] = []
        for sub in data.get("subdomains", []):
            fqdn = f"{sub}.{domain}".lower()
            if fqdn not in seen:
                seen.add(fqdn)
                out.append(fqdn)
        return out

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
```

- [ ] **Step 3.5 — Run tests to verify they pass**

Run: `make test`
Expected: 5 chaos tests pass.

- [ ] **Step 3.6 — Commit**

```bash
git add src/earn_money/recon/chaos.py tests/recon/test_chaos.py tests/fixtures/chaos_subdomains.json
git commit -m "feat: add Chaos API client for passive subdomain data"
```

---

## Task 4 — DNS resolver

**Files:**
- Create: `src/earn_money/recon/resolver.py`
- Create: `tests/recon/test_resolver.py`
- Modify: `pyproject.toml` (add `dnspython>=2.6`)

A thin wrapper around `dnspython` that resolves a host to a list of A records. The wrapper accepts an injected resolver so tests can control the response without touching real DNS. Returns an empty list on NXDOMAIN/timeout (not an error — that's just "no current A record").

- [ ] **Step 4.1 — Modify `pyproject.toml`**

Add `"dnspython>=2.6"` to the `dependencies` list. The full updated `[project]` table block:

```toml
[project]
name = "earn_money"
version = "0.0.1"
description = "Bug-bounty operations pipeline."
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "python-frontmatter>=1.1",
    "pyyaml>=6.0",
    "dnspython>=2.6",
]
```

Then run `make install-dev` to install the new dep before continuing.

- [ ] **Step 4.2 — Write the failing tests at `tests/recon/test_resolver.py`**

```python
from __future__ import annotations

from unittest.mock import MagicMock

import dns.exception
import pytest

from earn_money.recon import resolver


def test_resolve_returns_a_records(mocker: pytest.MonkeyPatch) -> None:
    fake_answer = [MagicMock(address="93.184.216.34"), MagicMock(address="93.184.216.35")]
    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = fake_answer

    ips = resolver.resolve_a("www.example.com", dns_resolver=fake_resolver)

    assert sorted(ips) == ["93.184.216.34", "93.184.216.35"]
    fake_resolver.resolve.assert_called_once_with("www.example.com", "A")


def test_resolve_returns_empty_on_nxdomain(mocker: pytest.MonkeyPatch) -> None:
    fake_resolver = MagicMock()
    fake_resolver.resolve.side_effect = dns.resolver.NXDOMAIN()
    assert resolver.resolve_a("missing.example.com", dns_resolver=fake_resolver) == []


def test_resolve_returns_empty_on_timeout(mocker: pytest.MonkeyPatch) -> None:
    fake_resolver = MagicMock()
    fake_resolver.resolve.side_effect = dns.exception.Timeout()
    assert resolver.resolve_a("slow.example.com", dns_resolver=fake_resolver) == []


def test_resolve_returns_empty_on_no_answer(mocker: pytest.MonkeyPatch) -> None:
    fake_resolver = MagicMock()
    fake_resolver.resolve.side_effect = dns.resolver.NoAnswer()
    assert resolver.resolve_a("no-a.example.com", dns_resolver=fake_resolver) == []


def test_make_default_resolver_uses_configured_nameservers() -> None:
    r = resolver.make_default_resolver(["1.1.1.1", "9.9.9.9"])
    assert r.nameservers == ["1.1.1.1", "9.9.9.9"]
    assert r.lifetime == 5.0
```

- [ ] **Step 4.3 — Run tests to verify they fail**

Run: `make test`
Expected: ImportError — `recon.resolver` does not exist.

- [ ] **Step 4.4 — Write `src/earn_money/recon/resolver.py`**

```python
"""DNS resolution. A-record only in Phase 2."""

from __future__ import annotations

import dns.exception
import dns.resolver


def make_default_resolver(nameservers: list[str]) -> dns.resolver.Resolver:
    """Return a Resolver configured to use the given recursive resolvers.

    Use a dedicated resolver (e.g. ``1.1.1.1`` on the VPS, or a self-hosted
    Unbound) — not the ISP default — to avoid leaking enumeration patterns.
    """
    r = dns.resolver.Resolver(configure=False)
    r.nameservers = list(nameservers)
    r.lifetime = 5.0
    return r


def resolve_a(host: str, *, dns_resolver: dns.resolver.Resolver) -> list[str]:
    """Return A-record IPs for ``host``. Empty list on NXDOMAIN/timeout/no-answer."""
    try:
        answer = dns_resolver.resolve(host, "A")
    except (
        dns.resolver.NXDOMAIN,
        dns.resolver.NoAnswer,
        dns.exception.Timeout,
        dns.resolver.NoNameservers,
    ):
        return []
    return [rdata.address for rdata in answer]
```

- [ ] **Step 4.5 — Run tests to verify they pass**

Run: `make test`
Expected: 5 resolver tests pass.

- [ ] **Step 4.6 — Commit**

```bash
git add pyproject.toml src/earn_money/recon/resolver.py tests/recon/test_resolver.py
git commit -m "feat: add DNS resolver with injected dns_resolver for testing"
```

---

## Task 5 — Asset upsert into SQLite

**Files:**
- Create: `src/earn_money/recon/assets.py`
- Create: `tests/recon/test_assets.py`

Inserts or updates rows in the per-program `assets` table from Phase 1 (Task 4). New subdomain → INSERT with `first_seen = last_seen = now`. Existing subdomain → UPDATE `last_seen` and `ip`/`ports`/`fingerprint` if changed.

The upsert is a single operation; the caller passes a list of discovered assets and a single `observed_at` timestamp.

- [ ] **Step 5.1 — Write the failing tests at `tests/recon/test_assets.py`**

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from earn_money import db
from earn_money.recon import assets


def _conn(tmp_path: Path) -> sqlite3.Connection:
    return db.open_db(tmp_path / "test.sqlite")


def test_upsert_inserts_new_assets(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    summary = assets.upsert_assets(
        conn,
        [
            assets.AssetObservation(subdomain="api.example.com", ips=["1.2.3.4"]),
            assets.AssetObservation(subdomain="www.example.com", ips=["5.6.7.8"]),
        ],
        observed_at="2026-05-12T08:00:00Z",
        in_scope=True,
    )
    assert summary.inserted == 2
    assert summary.updated == 0
    rows = conn.execute(
        "SELECT subdomain, ip, first_seen, last_seen, in_scope_at_observation "
        "FROM assets ORDER BY subdomain"
    ).fetchall()
    assert rows == [
        ("api.example.com", "1.2.3.4", "2026-05-12T08:00:00Z", "2026-05-12T08:00:00Z", 1),
        ("www.example.com", "5.6.7.8", "2026-05-12T08:00:00Z", "2026-05-12T08:00:00Z", 1),
    ]
    conn.close()


def test_upsert_updates_last_seen_for_known_assets(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="api.example.com", ips=["1.2.3.4"])],
        observed_at="2026-05-12T08:00:00Z",
        in_scope=True,
    )
    summary = assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="api.example.com", ips=["1.2.3.4"])],
        observed_at="2026-05-13T08:00:00Z",
        in_scope=True,
    )
    assert summary.inserted == 0
    assert summary.updated == 1
    (first_seen, last_seen) = conn.execute(
        "SELECT first_seen, last_seen FROM assets WHERE subdomain='api.example.com'"
    ).fetchone()
    assert first_seen == "2026-05-12T08:00:00Z"
    assert last_seen == "2026-05-13T08:00:00Z"
    conn.close()


def test_upsert_updates_ip_when_changed(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="api.example.com", ips=["1.2.3.4"])],
        observed_at="2026-05-12T08:00:00Z",
        in_scope=True,
    )
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="api.example.com", ips=["9.9.9.9"])],
        observed_at="2026-05-13T08:00:00Z",
        in_scope=True,
    )
    (ip,) = conn.execute(
        "SELECT ip FROM assets WHERE subdomain='api.example.com'"
    ).fetchone()
    assert ip == "9.9.9.9"
    conn.close()


def test_upsert_records_in_scope_flag(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="oos.example.com", ips=["1.1.1.1"])],
        observed_at="2026-05-12T08:00:00Z",
        in_scope=False,
    )
    (flag,) = conn.execute(
        "SELECT in_scope_at_observation FROM assets WHERE subdomain='oos.example.com'"
    ).fetchone()
    assert flag == 0
    conn.close()


def test_upsert_handles_empty_input(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    summary = assets.upsert_assets(conn, [], observed_at="2026-05-12T08:00:00Z", in_scope=True)
    assert summary.inserted == 0
    assert summary.updated == 0
    conn.close()


def test_upsert_joins_multiple_ips_with_comma(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    assets.upsert_assets(
        conn,
        [assets.AssetObservation(subdomain="api.example.com", ips=["1.1.1.1", "2.2.2.2"])],
        observed_at="2026-05-12T08:00:00Z",
        in_scope=True,
    )
    (ip,) = conn.execute(
        "SELECT ip FROM assets WHERE subdomain='api.example.com'"
    ).fetchone()
    assert ip == "1.1.1.1,2.2.2.2"
    conn.close()
```

- [ ] **Step 5.2 — Run tests to verify they fail**

Run: `make test`
Expected: ImportError — `recon.assets` does not exist.

- [ ] **Step 5.3 — Write `src/earn_money/recon/assets.py`**

```python
"""Asset upsert into the per-program SQLite assets table."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class AssetObservation:
    subdomain: str
    ips: list[str]


@dataclass(frozen=True)
class UpsertSummary:
    inserted: int
    updated: int


def upsert_assets(
    conn: sqlite3.Connection,
    observations: list[AssetObservation],
    *,
    observed_at: str,
    in_scope: bool,
) -> UpsertSummary:
    """Insert new assets, update last_seen and ip on known ones.

    Returns counts of inserted and updated rows. ``ips`` is stored as a
    comma-joined string in the ``ip`` column for grep-ability.
    """
    inserted = 0
    updated = 0
    flag = 1 if in_scope else 0

    for obs in observations:
        ip_str = ",".join(obs.ips)
        cursor = conn.execute(
            "SELECT subdomain FROM assets WHERE subdomain = ?",
            (obs.subdomain,),
        )
        if cursor.fetchone() is None:
            conn.execute(
                "INSERT INTO assets "
                "(subdomain, ip, ports, fingerprint, first_seen, last_seen, in_scope_at_observation) "
                "VALUES (?, ?, NULL, NULL, ?, ?, ?)",
                (obs.subdomain, ip_str, observed_at, observed_at, flag),
            )
            inserted += 1
        else:
            conn.execute(
                "UPDATE assets SET ip = ?, last_seen = ?, in_scope_at_observation = ? "
                "WHERE subdomain = ?",
                (ip_str, observed_at, flag, obs.subdomain),
            )
            updated += 1

    conn.commit()
    return UpsertSummary(inserted=inserted, updated=updated)
```

- [ ] **Step 5.4 — Run tests to verify they pass**

Run: `make test`
Expected: 6 assets tests pass.

- [ ] **Step 5.5 — Commit**

```bash
git add src/earn_money/recon/assets.py tests/recon/test_assets.py
git commit -m "feat: add asset upsert with first_seen/last_seen tracking"
```

---

## Task 6 — Passive-recon orchestrator and runner

**Files:**
- Create: `src/earn_money/runners/passive_recon.py`
- Create: `tests/runners/test_passive_recon.py`

The orchestrator composes everything from Phase 1 and Tasks 1–5:

1. `require_recon_enabled(paths)` (kill-switch from Phase 1).
2. Read `scope.md` for the program.
3. `require_policy_allows(scope, mode="passive")`.
4. `require_program_not_frozen(paths, platform, slug)`.
5. For each unique apex domain in `scope.in_scope`, run subfinder + Chaos in sequence, take the union, lowercase + dedupe.
6. For each candidate subdomain, check it matches an in-scope wildcard (or equals an explicit in-scope entry) — drop anything that doesn't, mark out-of-scope ones with `in_scope=False`.
7. Resolve each in-scope subdomain to A records (DNS).
8. Upsert into the per-program SQLite assets table with the current timestamp.
9. Return a `PassiveReconResult` with counts so the CLI can log.

The CLI `main()` matches Phase 1's pattern: argparse, env-var creds, exit codes (0 success, 1 unexpected, 2 RECON_ENABLED missing, 3 frozen, 4 policy violation).

**Apex extraction:** Phase 2 takes the apex from each in-scope entry by stripping a leading `*.` and using the rest as the seed for subfinder. For non-wildcard entries (e.g., `api.example.com`), the entry itself is treated as a known subdomain plus its apex is computed by dropping the leftmost label. This is intentionally simple — Phase 3 can refine.

- [ ] **Step 6.1 — Write the failing tests at `tests/runners/test_passive_recon.py`**

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from earn_money import config, flags, policy, scope
from earn_money.recon import chaos
from earn_money.runners import passive_recon


def _seed(paths: config.Paths, *, policy_value: scope.Policy, in_scope: list[str]) -> None:
    s = scope.Scope(
        platform="hackerone", slug="example", policy=policy_value,
        in_scope=in_scope, out_of_scope=[], notes="",
        scope_hash="seed", last_synced="2026-05-12T07:00:00Z",
    )
    scope.write_scope(paths.scope_file("hackerone", "example"), s)


def _chaos_client(payload: dict) -> chaos.Client:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)
    return chaos.Client(token="t", transport=httpx.MockTransport(handler))


def test_refuses_without_recon_enabled(tmp_repo: Path, mocker: pytest.MonkeyPatch) -> None:
    paths = config.Paths.from_root(tmp_repo)
    _seed(paths, policy_value="rate-limited-OK", in_scope=["*.example.com"])
    with pytest.raises(flags.ReconDisabled):
        passive_recon.run_program(
            paths, "hackerone", "example",
            chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
            dns_resolver=MagicMock(),
            subfinder_run=lambda d: [],
        )


def test_refuses_manual_only_policy(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="manual-only", in_scope=["*.example.com"])
    with pytest.raises(policy.PolicyViolation):
        passive_recon.run_program(
            paths, "hackerone", "example",
            chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
            dns_resolver=MagicMock(),
            subfinder_run=lambda d: [],
        )


def test_refuses_when_program_frozen(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="rate-limited-OK", in_scope=["*.example.com"])
    flags.freeze_program(paths, "hackerone", "example", reason="prior")
    with pytest.raises(flags.ProgramFrozen):
        passive_recon.run_program(
            paths, "hackerone", "example",
            chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
            dns_resolver=MagicMock(),
            subfinder_run=lambda d: [],
        )


def test_discovers_and_resolves_and_writes(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="rate-limited-OK", in_scope=["*.example.com"])

    chaos_client = _chaos_client(
        {"domain": "example.com", "subdomains": ["api", "www"]}
    )
    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = [MagicMock(address="1.2.3.4")]

    def subfinder_run(domain: str) -> list[str]:
        assert domain == "example.com"
        return ["api.example.com", "mail.example.com"]

    result = passive_recon.run_program(
        paths, "hackerone", "example",
        chaos_client=chaos_client,
        dns_resolver=fake_resolver,
        subfinder_run=subfinder_run,
    )

    assert result.subdomains_discovered == 3  # api, www, mail (api dedup'd)
    assert result.assets_upserted >= 3
    # Verify SQLite write.
    import sqlite3
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain, ip FROM assets ORDER BY subdomain").fetchall()
    conn.close()
    assert sorted(r[0] for r in rows) == [
        "api.example.com", "mail.example.com", "www.example.com"
    ]
    # All three resolved to 1.2.3.4.
    assert all(r[1] == "1.2.3.4" for r in rows)


def test_drops_out_of_scope_subdomains(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="rate-limited-OK", in_scope=["api.example.com"])

    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = []

    def subfinder_run(_: str) -> list[str]:
        return ["api.example.com", "other.example.com"]

    result = passive_recon.run_program(
        paths, "hackerone", "example",
        chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
        dns_resolver=fake_resolver,
        subfinder_run=subfinder_run,
    )

    # other.example.com is out of scope (in_scope only lists exact api.example.com).
    assert result.subdomains_discovered == 1
    import sqlite3
    conn = sqlite3.connect(paths.program_db("hackerone", "example"))
    rows = conn.execute("SELECT subdomain FROM assets").fetchall()
    conn.close()
    assert [r[0] for r in rows] == ["api.example.com"]


def test_wildcard_match_includes_descendants(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    _seed(paths, policy_value="rate-limited-OK", in_scope=["*.example.com"])

    fake_resolver = MagicMock()
    fake_resolver.resolve.return_value = []

    def subfinder_run(_: str) -> list[str]:
        return ["api.example.com", "deep.nested.example.com", "evil.com"]

    result = passive_recon.run_program(
        paths, "hackerone", "example",
        chaos_client=_chaos_client({"domain": "example.com", "subdomains": []}),
        dns_resolver=fake_resolver,
        subfinder_run=subfinder_run,
    )

    # evil.com is out of scope — wildcard *.example.com matches only example.com descendants.
    assert result.subdomains_discovered == 2
```

- [ ] **Step 6.2 — Run tests to verify they fail**

Run: `make test`
Expected: ImportError — `runners.passive_recon` does not exist.

- [ ] **Step 6.3 — Write `src/earn_money/runners/passive_recon.py`**

```python
"""Passive-recon runner. Cron entry point — passive subdomain discovery only."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import dns.resolver

from earn_money import config, db, flags, policy, scope
from earn_money.recon import assets, chaos, resolver, subfinder

SubfinderRun = Callable[[str], list[str]]


@dataclass(frozen=True)
class PassiveReconResult:
    subdomains_discovered: int
    assets_upserted: int


def _apexes_from_in_scope(in_scope: list[str]) -> set[str]:
    """Return the set of apex domains to feed subfinder/chaos."""
    apexes: set[str] = set()
    for entry in in_scope:
        bare = entry.removeprefix("*.").lower()
        # Drop the leftmost label for non-wildcard entries to get the apex.
        if entry.startswith("*."):
            apexes.add(bare)
        else:
            parts = bare.split(".")
            if len(parts) >= 2:
                apexes.add(".".join(parts[-2:]))
            else:
                apexes.add(bare)
    return apexes


def _is_in_scope(fqdn: str, in_scope: list[str]) -> bool:
    fqdn = fqdn.lower()
    for entry in in_scope:
        entry_l = entry.lower()
        if entry_l == fqdn:
            return True
        if entry_l.startswith("*."):
            suffix = entry_l[2:]
            if fqdn.endswith("." + suffix) or fqdn == suffix:
                return True
    return False


def run_program(
    paths: config.Paths,
    platform: str,
    slug: str,
    *,
    chaos_client: chaos.Client,
    dns_resolver: dns.resolver.Resolver,
    subfinder_run: SubfinderRun = subfinder.enumerate_subdomains,
) -> PassiveReconResult:
    """Run passive recon for one program. See the plan for the ordered steps."""
    flags.require_recon_enabled(paths)
    flags.require_program_not_frozen(paths, platform, slug)

    if platform != "hackerone":
        raise ValueError(f"platform {platform!r} not supported in Phase 2")

    s = scope.read_scope(paths.scope_file(platform, slug))
    policy.require_policy_allows(s, mode="passive")

    apexes = _apexes_from_in_scope(s.in_scope)

    candidates: set[str] = set()
    for apex in sorted(apexes):
        for sub in subfinder_run(apex):
            candidates.add(sub.lower())
        for sub in chaos_client.fetch_subdomains(apex):
            candidates.add(sub.lower())

    in_scope_candidates = sorted(c for c in candidates if _is_in_scope(c, s.in_scope))

    observed_at = datetime.now(UTC).isoformat(timespec="seconds")
    observations: list[assets.AssetObservation] = []
    for sub in in_scope_candidates:
        ips = resolver.resolve_a(sub, dns_resolver=dns_resolver)
        observations.append(assets.AssetObservation(subdomain=sub, ips=ips))

    db_path = paths.program_db(platform, slug)
    conn = db.open_db(db_path)
    try:
        summary = assets.upsert_assets(
            conn, observations, observed_at=observed_at, in_scope=True
        )
    finally:
        conn.close()

    return PassiveReconResult(
        subdomains_discovered=len(in_scope_candidates),
        assets_upserted=summary.inserted + summary.updated,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="passive-recon")
    parser.add_argument("--platform", default="hackerone")
    parser.add_argument("--program", required=True)
    parser.add_argument("--root", default=Path.cwd(), type=Path)
    parser.add_argument(
        "--resolver",
        action="append",
        default=None,
        help="Recursive resolver IP (repeat for multiple). Defaults to 1.1.1.1 + 9.9.9.9.",
    )
    args = parser.parse_args(argv)

    nameservers = args.resolver or ["1.1.1.1", "9.9.9.9"]
    paths = config.Paths.from_root(args.root)

    try:
        chaos_token = os.environ.get("CHAOS_API_TOKEN", "")
        chaos_client = chaos.Client(token=chaos_token)
    except chaos.ChaosAPIError as e:
        print(f"passive-recon: {e}", file=sys.stderr)
        return 1

    dns_resolver = resolver.make_default_resolver(nameservers)

    try:
        result = run_program(
            paths, args.platform, args.program,
            chaos_client=chaos_client,
            dns_resolver=dns_resolver,
        )
    except flags.ReconDisabled as e:
        print(f"passive-recon: {e}", file=sys.stderr)
        return 2
    except flags.ProgramFrozen as e:
        print(f"passive-recon: {e}", file=sys.stderr)
        return 3
    except policy.PolicyViolation as e:
        print(f"passive-recon: {e}", file=sys.stderr)
        return 4
    except Exception as e:
        print(
            f"passive-recon: unexpected error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1
    finally:
        chaos_client.close()

    print(
        f"passive-recon: discovered={result.subdomains_discovered} "
        f"upserted={result.assets_upserted}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6.4 — Run tests to verify they pass**

Run: `make test`
Expected: 6 passive-recon tests pass.

- [ ] **Step 6.5 — Commit**

```bash
git add src/earn_money/runners/passive_recon.py tests/runners/test_passive_recon.py
git commit -m "feat: add passive-recon runner composing subfinder, Chaos, DNS, and asset upsert"
```

---

## Task 7 — CLI wrapper and operator docs update

**Files:**
- Create: `bin/passive-recon`
- Modify: `programs/README.md` (append a "Passive recon" section)

The shell wrapper mirrors `bin/scope-sync`: loads `.env`, validates `.venv`, then execs into `python -m earn_money.runners.passive_recon`.

- [ ] **Step 7.1 — Write `bin/passive-recon`**

```sh
#!/bin/sh
# Thin wrapper around the passive-recon runner.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/.env"
  export HACKERONE_API_USERNAME HACKERONE_API_TOKEN CHAOS_API_TOKEN
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "passive-recon: .venv not found at $ROOT/.venv — run 'make install-dev' first" >&2
  exit 1
fi

exec "$ROOT/.venv/bin/python" -m earn_money.runners.passive_recon --root "$ROOT" "$@"
```

- [ ] **Step 7.2 — Make it executable**

Run: `chmod +x bin/passive-recon`

- [ ] **Step 7.3 — Smoke test**

Run: `bin/passive-recon --help`
Expected: argparse help text. Exit code 0.

- [ ] **Step 7.4 — Append a "Passive recon" section to `programs/README.md`**

Append the following to the end of `programs/README.md`:

```markdown

## Passive recon (Phase 2)

After `bin/scope-sync` has populated the program's in-scope list, you can run passive recon to discover subdomains and persist them in the program's SQLite store.

### Prerequisites (one-time per VPS)

- Install `subfinder`:
  ```bash
  go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
  ```
  Verify with `subfinder -version`.
- Add a Chaos API token to `.env`:
  ```
  CHAOS_API_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  ```

### Run

```bash
bin/passive-recon --program <slug>
```

Optional flags:

- `--resolver 1.1.1.1` (repeatable) — pick the recursive DNS resolvers. Defaults to `1.1.1.1` and `9.9.9.9`. On a production VPS, prefer a dedicated or self-hosted resolver to avoid leaking enumeration patterns to your hosting provider's DNS.

### Output

Stdout: `passive-recon: discovered=<n> upserted=<n>`.

The per-program SQLite database at `programs/hackerone/<slug>/db.sqlite` now contains rows in the `assets` table — one per discovered, in-scope subdomain, with `first_seen`, `last_seen`, comma-joined `ip`, and `in_scope_at_observation`. This file is gitignored; do not commit it.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Unexpected error (network, Chaos credentials missing, etc.) |
| 2 | `RECON_ENABLED` absent |
| 3 | Program is frozen — review `programs/hackerone/<slug>/FROZEN`, fix, and remove |
| 4 | Policy violation — the program is `manual-only` and refuses automated recon |

### What does NOT happen in Phase 2

- No HTTP probing. `httpx` against the discovered subdomains is Phase 3.
- No daily digest. `ops/daily-digest.md` is Phase 3.
- No active-recon (nuclei, katana, ffuf). Phase 3+.
```

- [ ] **Step 7.5 — Run `make smoke`** to confirm no regressions

Run: `make smoke`
Expected: lint + mypy + all tests pass.

- [ ] **Step 7.6 — Commit**

```bash
git add bin/passive-recon programs/README.md
git commit -m "feat: add bin/passive-recon wrapper and operator docs for Phase 2"
```

---

## End-of-plan check

By the time all 7 tasks are done, all of the following must be true:

- [ ] `make smoke` exits 0 (ruff clean, mypy clean, all tests pass).
- [ ] `bin/passive-recon --help` prints help and exits 0.
- [ ] The pre-commit hook still blocks staged sensitive paths (re-confirm with a `.env` test).
- [ ] No source file (under `src/`, `tests/`, `bin/`, `scripts/`) exceeds 200 lines.
- [ ] `git status` is clean.
- [ ] `programs/README.md` has the new "Passive recon" section.
- [ ] `pyproject.toml` lists `dnspython>=2.6`.
- [ ] All recon traffic in tests goes through mocks. No test makes a real network call.

If everything above is green, Phase 2 is done. Phase 3 (active recon: httpx probing + nuclei + daily digest + chat-bus phone ping) gets its own plan.
