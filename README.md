# earn-money

Private operations repo for a continuous bug-bounty pipeline built around `clawpwn`. Phase 2 (deferred): a self-serve FITS Express mini-audit product.

This repository is **private** and operational. It is not a published product. The contents include scope definitions, recon configuration, finding workflows, and report templates. Sensitive operational artefacts (raw recon outputs, identity, payout config, per-program SQLite state, the `RECON_ENABLED` kill-switch) are gitignored and live only on the operator's machine.

## Status

A five-step-algorithm pass on 2026-05-12 (both reviewers agreed 100%) cut a lot of pre-emptive automation in favour of shipping the smallest earning loop first. Decision record: [`docs/superpowers/decisions/2026-05-12-five-step-cut.md`](docs/superpowers/decisions/2026-05-12-five-step-cut.md).

| Phase | What it ships | State |
|---|---|---|
| Phase 1 | Foundation — repo skeleton, scope-sync runner, kill-switch + freeze flags | ✅ Shipped |
| Phase 2 | Passive recon — `subfinder` + Chaos + DNS resolution → SQLite | ✅ Shipped (1 program: `hackerone/security`) |
| Phase 3a | Active recon foundation + `httpx` runner, migration framework, watchdog | ✅ Shipped (195 tests after 6 hygiene cycles) |
| Phase 3b | `nuclei` runner + triage engine v1 + expanded `findings` schema | ✅ Shipped |
| Phase 3c | `katana` crawler + `ffuf` content fuzzer | 🅿️ Parked — only unpark on specific signals (see decision record) |
| Phase 3d | 08:00 daily digest + phone ping + `bin/ack-freeze` | 🅿️ Mostly parked; **only** `bin/ack-freeze` shell helper kept |
| Phase 4 | First submission loop — `bin/draft` + `bin/submit` + `bin/ack-freeze` + report template | ✅ Shipped (226 tests; live-verified on VPS against `hackerone/security`) |
| Phase 5 | Operate one program, measure earnings, month-3 kill/pivot gate | 🟡 Measure-not-build |
| Phase 6 | FITS Express mini-audit product | ❌ Dropped from active roadmap |

## Design

The full design is in [`docs/superpowers/specs/2026-05-12-earn-money-design.md`](docs/superpowers/specs/2026-05-12-earn-money-design.md). The Phase 3 umbrella architecture is in [`docs/superpowers/specs/2026-05-12-phase-3-design.md`](docs/superpowers/specs/2026-05-12-phase-3-design.md). Per-sub-phase implementation plans live in [`docs/superpowers/plans/`](docs/superpowers/plans/). Operational hard rules are duplicated in [`CLAUDE.md`](CLAUDE.md).

Key invariants:

- **Scope is gospel.** No scan against an asset not in the current `scope.md`. Wildcards resolve at scan time; every resolved asset is OOS-checked before any traffic is sent.
- **Two human gates.** `_queue → _verified` and `_verified → _submitted` both require the operator. No automated submission. Reports require substantive human edit.
- **Three-tier program policy.** `rate-limited-OK`, `manual-only`, `ambiguous`. Recon runners refuse to run when the policy forbids it.
- **`RECON_ENABLED` flag file is the master kill-switch.** Every runner checks for it on every invocation. Removing the file halts the entire pipeline within ~10 seconds (active runners have a watchdog thread that polls every 5 s).

## Local setup

Clone, then install the git hooks:

```bash
./scripts/install-hooks.sh
```

The `pre-push` hook is owner-locked to `github.com/cocodedk` — pushing this repo to any other GitHub owner will fail.

Set up the Python virtualenv and install dev deps:

```bash
make install-dev
```

External tools (must be on `PATH`):

- `subfinder` v2+ (passive subdomain enumeration, Phase 2)
- `httpx` v1.9+ from ProjectDiscovery (active HTTP probing, Phase 3a). Note: the PyPI `httpx` is a different tool (Python HTTP client library); install the Go one from `github.com/projectdiscovery/httpx/cmd/httpx`.
- `nuclei` v3+ (template-based vuln scan, Phase 3b)
- `katana`, `ffuf` (Phase 3c — currently parked)

## VPS setup (first-run)

The CLAUDE.md hard rule: live recon traffic exits via the dedicated VPS, never the laptop. Setup is one-shot:

```bash
# 1. Provision a fresh Ubuntu 24.04+ VPS, SSH in as root.
# 2. On the VPS, run the installer:
curl -fsSL https://raw.githubusercontent.com/cocodedk/earn-money/main/scripts/install-vps.sh | sh
# Or rsync the repo first (recommended; the installer prints the rsync command).
```

The script installs `subfinder` / `httpx` / `nuclei` from ProjectDiscovery's prebuilt releases, fetches `nuclei-templates`, and prints the rsync + .env + venv commands to run from the laptop. Full operator routine after setup: [`ops/playbook.md`](ops/playbook.md).

## Common operations

Local (laptop):

```bash
make smoke               # full lint + tests (also runs as the pre-commit hook)
make lint                # ruff + mypy strict
make test                # pytest
```

Recon (laptop or VPS — VPS-only for live programs per the egress-IP rule):

```bash
bin/scope-sync                       # Phase 1: refresh each program's scope.md from its platform
bin/passive-recon --program <slug>   # Phase 2: discover subdomains for one program (no traffic to target)
bin/httpx-probe   --program <slug>   # Phase 3a: HTTP-fingerprint discovered assets (live traffic)
bin/nuclei-scan   --program <slug>   # Phase 3b: template-based vuln scan (live traffic, rate-capped)
bin/triage        --program <slug>   # Phase 3b: convert untriaged signals into findings/_queue/<hash>.md
```

Submission loop (the two human gates):

```bash
bin/draft  --program <slug> --hash <full-hash>            # write reports/drafts/<hash>.md from the verified finding
bin/submit --program <slug> --hash <full-hash> \
           --report-id H1-XXXXXXX --note "..."            # mark verified → submitted in the DB

bin/ack-freeze <platform>/<slug>                          # acknowledge a scope-diff freeze; $EDITOR for the reason
```

Master kill-switch (operator's explicit consent gate; gitignored):

```bash
touch RECON_ENABLED      # arm
rm RECON_ENABLED         # halt the pipeline within ~10 seconds
```

Full operator routine: see [`ops/playbook.md`](ops/playbook.md).

## Glossary

Acronyms from four overlapping disciplines (engineering, security, tools, infrastructure) live in [`docs/glossary.md`](docs/glossary.md). Start there if a term is unfamiliar.

<!-- inline glossary moved to docs/glossary.md -->

## Author

**Babak Bandpey** — [cocode.dk](https://cocode.dk) | [LinkedIn](https://linkedin.com/in/babakbandpey) | [GitHub](https://github.com/cocodedk)

## License

Apache-2.0 | © 2026 [Cocode](https://cocode.dk)
