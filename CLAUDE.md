# CLAUDE.md — earn-money

## Project status

**v2 fresh start (2026-05-18).** The full v1 corpus — bug-bounty pipeline built around `clawpwn`, with recon runners, agent, dashboard, triage, and reporting — is parked under [`archive/v1/`](archive/v1/). Tag [`v1-final`](https://github.com/cocodedk/earn-money/releases/tag/v1-final) marks its complete state.

The active direction is the [vuln-scanning cookbook](docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/): 278 leaf-bullet specs across 24 phases of OWASP / PortSwigger coverage, each filled in by GPT-5.5 enrichment then implemented in TDD against the test fixtures on `target.cocode.dk`.

- **Owner**: Babak Bandpey ([cocode.dk](https://cocode.dk))
- **Visibility**: public — the pre-push hook refuses pushes to non-cocodedk remotes
- **v1 reference**: full v1 rules and design live in [`archive/v1/CLAUDE.md`](archive/v1/CLAUDE.md)

## Required skills — ALWAYS invoke these

| Situation | Skill |
|-----------|-------|
| Before any new feature or component | `superpowers:brainstorming` |
| Planning multi-step changes | `superpowers:writing-plans` |
| Writing or fixing core logic | `superpowers:test-driven-development` |
| First sign of a bug or failure | `superpowers:systematic-debugging` |
| Before completing a feature branch | `superpowers:requesting-code-review` |
| Before claiming any task done | `superpowers:verification-before-completion` |
| Working on UI / frontend | `frontend-design:frontend-design` |
| After implementing — reviewing quality | `simplify` |

## Hard rules — apply to any v2 code that ships

These project-wide invariants survived from v1; they govern any active recon or scanning code under this repo.

### Scope is gospel
- No scan, probe, or DNS lookup of an asset not in the program's `scope.md`.
- Wildcard scopes resolve at scan time; every resolved asset is OOS-checked.
- Destructive scope diff or sync failure → write per-program freeze flag.

### Two human gates
- `findings/_queue/ → findings/_verified/` requires the operator.
- `findings/_verified/ → findings/_submitted/` requires `bin/submit`. No automatic submission, ever.
- Reports require substantive operator edit. Templates are starting drafts.

### Three-tier program policy
- `rate-limited-OK` — automated scanning permitted within rate limits.
- `manual-only` — automated scanning prohibited; runners refuse to start.
- `ambiguous` — passive recon only until program clarifies.

### Kill-switch
- `RECON_ENABLED` flag file at repo root is the master switch.
- Per-program freeze flags gate per-program recon independently.

### Per-program Rules of Engagement
- Every `programs/<platform>/<slug>/` carries a `roe.md` declaring technique-level authority. Loaded at runtime by active runners.
- Default floor (unless `roe.md` overrides): no social engineering, no DoS, no destructive payloads.
- GDPR Art. 28 on real third-party PII: `roe.md` must specify `pii_handling: synthetic_data_only`, or use program-supplied test data.

### Operational rules
- Never commit `recon/outputs/`, `identity/platforms.md`, `RECON_ENABLED`, or any `*.sqlite`. Gitignored for both root and `archive/v1/`; pre-commit hook refuses anyway.
- One handle per platform. No sock-puppets.
- Coordinated disclosure. No public writeup until program permits.
- VPS egress IP is for nothing else. No SSH-from-laptop traffic.

## Test fixtures

Operator-owned vuln-app host at `target.cocode.dk` (`89.167.63.167`). Four publicly-reachable HTTPS endpoints serve as cookbook fixtures:

| URL | App | Notes |
|-----|-----|-------|
| `https://target.cocode.dk/` | OWASP Juice Shop | "Mystery" blind target — no hostname leak, no path leak; runners must fingerprint. |
| `https://juiceshop.cocode.dk/` | OWASP Juice Shop | Same container, identifiable hostname. |
| `https://dvwa.cocode.dk/` | DVWA | Default creds `admin` / `password`. DB auto-created via MariaDB sidecar `dvwa-db` on docker network `dvwa-net` — DVWA container needs `DB_SERVER=dvwa-db` env or login breaks. |
| `https://webgoat.cocode.dk/` | WebGoat | Root redirects to `/WebGoat/login`. Self-service registration; no default admin. |

All four URLs are authorised for any HTTP technique — the `roe.md` floor applies to live bug-bounty programs, not these designated test environments. Caddy config: `/etc/caddy/Caddyfile` on the host. SSH: `root@target.cocode.dk` with `~/.ssh/id_cocodedk`. Eight additional lab containers (clawpwn variants, JBoss/WebLogic CVE labs, extra Juice Shop replicas) are reachable only on `127.0.0.1:18xxx` from the host itself — add a Caddy block when a cookbook bullet needs one.

## Engineering principles

### File size
**200-line maximum per file** for code, tests, HTML, CSS, JS, and config. Extract when approaching the limit. Spec/plan files under `docs/superpowers/` are exempt from the line cap but must be split into a subfolder of short focused files — the cookbook tree follows this pattern.

### DRY · SOLID · KISS · YAGNI
- Extract shared logic. Never copy-paste.
- Single responsibility per class and function.
- No features not yet needed.
- Delete dead code immediately.

### TDD — strict, 100% coverage required

- **TDD only.** Every new function, branch, model behaviour, API endpoint, runner, or CLI starts with a failing test. No production code is written before its test. Refactors keep tests green before and after.
- **100% line + branch coverage on the production code path.** "Production code" means anything that runs inside the deployed scanner platform — currently `backend/apps/`, future runners under `backend/`, and any future scanner stub implementations. Coverage is measured in CI on this scope and refused below 100%.
- **Repo-maintenance tooling is outside the bar.** Scripts under `scripts/` that manage the spec tree (`cookbook_progress.py`, `cookbook_bootstrap.py`, `cookbook_templates.py`) are dev-time tools, not platform code. They're tested when materially refactored, not retroactively. If a maintenance script grows real logic that runs at scan time, it migrates into `backend/` and joins the strict-TDD scope.
- **Pragmatic exclusions** (and ONLY these) are allowed even inside the strict scope:
  - `if __name__ == "__main__":` guards
  - Django `apps.py`, `migrations/`, `wsgi.py`, `asgi.py` (framework boilerplate)
  - Trivial `__str__` on Django models (one-line `return f"..."`)
  - Any `# pragma: no cover` line must justify itself in a comment on the same line
- **Test names describe behaviour**: `test_refuses_active_recon_when_policy_manual_only`, not `test_recon`.
- **Recon runners get integration tests against a mock target before any real asset** — never point a runner at a live target before the test exists.

### Commit hygiene
- Conventional Commits enforced by the `commit-msg` hook.
- Branch naming: `<type>/<short-description>` in kebab-case. See `CONTRIBUTING.md`.
- Never `--no-verify` unless explicitly authorised. Hook failures are signals, not noise.

## Behavioural guidelines

Carried forward from v1 unchanged. See [`archive/v1/CLAUDE.md`](archive/v1/CLAUDE.md) "Behavioural guidelines" section for the full text: *Think before coding · Simplicity first · Surgical changes · Goal-driven execution.*

## Key files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | This file — operational rules for v2 |
| `docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/` | Cookbook spec tree (278 bullets, 24 phases) |
| `docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/00-shared-schema.md` | Paste-ready spec contract — shared types, enums, coding-agent rules |
| `docs/superpowers/plans/2026-05-18-VULN-SCANNING-COOKBOOK/` | Mirror plan tree |
| `scripts/cookbook_progress.py` | Reads frontmatter → regenerates `PROGRESS.md` |
| `scripts/cookbook_bootstrap.py` | Idempotent migrator; `--apply` required to write |
| `scripts/cookbook_templates.py` | Templates and section schemas |
| `archive/v1/` | Parked v1 corpus — full pipeline, code, tests, docs |
| `archive/v1/CLAUDE.md` | v1 operational rules and design spec link |
| `.gitignore` | Sensitive paths locked down (both root and `archive/v1/`) |
| `.githooks/pre-push` | Owner-locked to `cocodedk` |

## Starting a new session

1. Read this file in full.
2. Read [`docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/README.md`](docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/README.md) for the cookbook workflow.
3. Read [`docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/00-shared-schema.md`](docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/00-shared-schema.md) for the paste-ready spec contract.
4. Check [`docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/PROGRESS.md`](docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/PROGRESS.md) for current cookbook state.
5. Verify `git status` — no untracked sensitive files.
6. Verify the active gh account is `cocodedk` (`gh auth status`).
7. Follow the required skills table — every skill is mandatory.
