# CLAUDE.md — earn-money

## Project overview

Private operational repository for a continuous bug-bounty pipeline built around `clawpwn`. The full design is in [`docs/superpowers/specs/2026-05-12-earn-money-design.md`](docs/superpowers/specs/2026-05-12-earn-money-design.md) — read it before any non-trivial work.

- **Language / Runtime**: Python 3.12+ for runners and orchestration; shell for installers and CLIs; SQLite for per-program state.
- **Owner**: Babak Bandpey ([cocode.dk](https://cocode.dk))
- **Visibility**: private — never push to a non-cocodedk remote.

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

## Hard rules — these override everything else

These rules come from the design spec. Breaking any of them is a stop-the-world event.

### Scope is gospel

- No scan, no probe, no DNS lookup of an asset that is not in the current `scope.md` for that program.
- Wildcard scopes resolve at scan time; each resolved asset is checked against the program's explicit OOS blocklist before any traffic is sent.
- If scope sync detects a destructive diff (asset moved OOS) or fails for any reason, the per-program freeze flag is written and recon halts for that program until the operator explicitly acks.

### Two human gates

- `findings/_queue/ → findings/_verified/` requires the operator. Claude cannot promote autonomously.
- `findings/_verified/ → findings/_submitted/` requires the operator to run `bin/submit` explicitly. There is no automatic submission, ever.
- Reports must read as written by a human expert. Templates are starting drafts, not finished products. Substantive operator edit pass, not cosmetic.

### Three-tier program policy

Every `scope.md` declares one `policy:` value. Recon runners refuse to run when the policy forbids it.

- **`rate-limited-OK`** — automated scanning permitted (within program rate limits). Full pipeline.
- **`manual-only`** — automated scanning prohibited. Operator scans by hand. Claude only maintains `scope.md`, tracks `findings/` state, and drafts reports from operator notes. **Recon runners refuse to start against any program with this flag.** Slowing automated traffic does not convert a `manual-only` program into `rate-limited-OK`; the discriminator is agent, not rate.
- **`ambiguous`** — ToS unclear. Written clarification requested from the program; reply saved in `programs/<slug>/notes.md`. Passive recon only (Chaos, Shodan, archive data — no live probing) until the program replies.

### Kill-switch

- The `RECON_ENABLED` flag file in the repo root is the master switch. Every runner checks for its presence on every cron invocation, not just at boot. Removing the file halts the entire pipeline immediately.
- Per-program freeze flags (written by the scope-sync runner on destructive scope diffs) gate per-program recon independently of the master switch.

### Operational rules

- Never commit `recon/outputs/`, `identity/platforms.md`, `RECON_ENABLED`, or any `*.sqlite` file. These are gitignored; verify before every commit.
- One handle per platform. No sock-puppets. No multi-account.
- No social engineering, no DoS, no destructive payloads — even where a program technically permits them.
- No PII exfiltration. One redacted screenshot as proof-of-concept, then stop.
- Coordinated disclosure. No public writeup until the program permits (default 90-day silence + program approval).
- The dedicated VPS egress IP is used for nothing else. No SSH-from-laptop traffic, no personal services. Triage teams cross-reference IPs.

## Architecture

See the spec for the full breakdown. Five units with clear boundaries:

1. **Program registry** (`programs/<platform>/<slug>/`) — single source of truth on scope, policy tier, and program-specific notes.
2. **Recon runners** (`recon/runners/`) — clawpwn wrappers per asset class. Pure functions: scope → artefacts.
3. **Triage / hypothesis engine** — reads recon artefacts + SQLite, drops candidates into `findings/_queue/`. Cannot advance past gate 1.
4. **Report drafter** — for each `_verified/` item, produces a platform-ready draft in `reports/drafts/`.
5. **Ledger + retro** — updates `ops/ledger.md` on every state transition; monthly retro auto-generated.

Layer rules: runners never read from `findings/`; report drafter never writes to `_queue/` or `_verified/`; the ledger is append-only and never edited by hand.

## Coding conventions

- All state changes go through SQLite or explicit file moves — never duplicate state between sources.
- Functions are pure where possible. Side effects are isolated to runners and CLIs.
- Strict typing in Python (`from __future__ import annotations`, full type hints, `mypy --strict`).
- No hardcoded program names, asset IDs, or scope rules in code. Everything lives in `programs/<platform>/<slug>/scope.md` and is read at runtime.

## Engineering principles

### File size

**200-line maximum per file.** Extract a class, function, or module when approaching the limit. Spec and plan files under `docs/superpowers/` are exempt — they are reference documents, not source.

### DRY · SOLID · KISS · YAGNI

- Extract shared logic into named utilities; never copy-paste.
- Single responsibility per class and function.
- Don't add features not yet needed. The roadmap (Phases 1–6 in the spec) is the only feature plan.
- Delete dead code immediately.

### TDD

- Write the failing test first, make it pass, then refactor.
- Test names describe behaviour: `"refuses_active_recon_when_policy_manual_only"`.
- One assertion per test where feasible. Keep tests focused.
- Recon runners get integration tests against a mock target before they ever touch a real asset.

### Commit hygiene

- Conventional Commits enforced by the `commit-msg` hook: `feat: ...` / `fix: ...` / `chore: ...` etc.
- Branch naming: `<type>/<short-description>` in kebab-case. See `CONTRIBUTING.md`.
- Never `--no-verify` unless explicitly authorised. Hook failures are signals, not noise.

## Behavioural guidelines

Adapted from Andrej Karpathy's [CLAUDE.md](https://github.com/forrestchang/andrej-karpathy-skills/blob/main/CLAUDE.md). These bias toward caution over speed. For trivial tasks, use judgement.

### Think before coding

Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### Simplicity first

Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### Surgical changes

Touch only what you must. Clean up only your own mess.

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

### Goal-driven execution

Define success criteria. Loop until verified.

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass."
- "Fix the bug" → "Write a test that reproduces it, then make it pass."
- "Refactor X" → "Ensure tests pass before and after."

For multi-step tasks, state a brief plan:

```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

**These guidelines are working when:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## Build / test / lint commands

```bash
# Stubs — wired up as the runners land.
make smoke          # full smoke check (lint + tests) — used by pre-commit hook
make lint           # ruff + shellcheck
make test           # pytest
```

Until `make` exists, the pre-commit hook is a no-op stub. Add the verification command to the hook the moment the first runner lands.

## Key files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | This file — operational rules and session startup |
| `docs/superpowers/specs/2026-05-12-earn-money-design.md` | Full design spec |
| `.gitignore` | Locks down sensitive paths — verify before every commit |
| `.githooks/pre-push` | Owner-locked to cocodedk; refuses pushes to other GitHub owners |
| `RECON_ENABLED` | Local kill-switch flag file (gitignored) |
| `scripts/install-hooks.sh` | One-time hook installer for fresh clones |
| `scripts/setup-repo.sh` | One-time branch protection setup |

## Starting a new session

1. Read this file in full.
2. Read the design spec at `docs/superpowers/specs/2026-05-12-earn-money-design.md`.
3. Verify `git status` — there should be no untracked sensitive files.
4. Verify the active gh account is `cocodedk` (`gh auth status`).
5. Check the current phase against the spec's "Phasing" section before proposing work.
6. Invoke `superpowers:brainstorming` before touching any feature.
7. Follow the required skills table — every skill is mandatory, not optional.
