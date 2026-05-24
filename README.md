# earn-money

Automated vulnerability scanning platform with an LLM-driven agent layer.

## Current state

**V3 agent** — an LLM (DeepSeek V4 Pro via OpenRouter) drives a Playwright browser through recon → enumerate → probe → verify → report phases against target web apps. The controller validates every action against phase/budget/RoE/scope gates before execution. ~50 deterministic v2 stubs remain as fast pre-pass tools the agent invokes via `run_stub`.

**Stack:** Django REST Framework backend, React/TypeScript frontend, Celery + Redis task queue, PostgreSQL, Playwright for browser automation, Caddy reverse proxy. All containerized via Docker Compose.

**Mission viewer** — frontend page at `/missions/:sessionId` streams the agent's turn-by-turn timeline via SSE: LLM reasoning, controller decisions, observations, phase transitions, and budget state in real time.

## Architecture

```
Frontend (React)  ──→  Django REST API  ──→  Celery Worker
     ↕ SSE                  ↕                    ↕
  Mission Viewer     AgentSession model    MissionController
                     (audit snapshot)      ├─ LLM Provider (OpenRouter/Anthropic)
                                           ├─ PlaywrightDriver (browser)
                                           └─ BudgetTracker + PlateauDetector
```

## Layout

```
backend/apps/agent/         ← V3 agent: controller, providers, browser driver, models
backend/apps/stubs/         ← V2 deterministic stub runners (Phases 1-3)
backend/apps/scans/         ← ScanRun lifecycle + Celery tasks
backend/apps/events/        ← Unified event log + SSE streaming
backend/apps/findings/      ← Finding + Evidence persistence
frontend/                   ← React/TS dashboard + mission viewer
fixtures/                   ← Lab fixture containers (session-cookie-lab, reset-canary, oauth-lab)
docs/superpowers/specs/     ← Cookbook specs (278 stubs) + V3 agent architecture
docs/superpowers/plans/     ← Implementation plans
scripts/                    ← Cookbook progress, sync-vps, hooks
archive/v1/                 ← Parked v1 corpus
```

## Test fixtures

Operator-owned lab host at `target.cocode.dk` / `h1.cocode.dk`:

| URL | App |
|-----|-----|
| `https://juiceshop.cocode.dk/` | OWASP Juice Shop |
| `https://dvwa.cocode.dk/` | DVWA (`admin`/`password`) |
| `https://webgoat.cocode.dk/` | WebGoat (self-registration) |
| `https://target.cocode.dk/` | Juice Shop (blind — no hostname leak) |

All authorised for any HTTP technique against these designated test environments.

## Local setup

```bash
cp .env.example .env          # fill in secrets
./scripts/install-hooks.sh    # pre-commit + pre-push + commit-msg hooks
docker compose up --build     # full stack at http://localhost
```

### Environment variables

| Variable | Purpose |
|----------|---------|
| `AGENT_LLM_PROVIDER` | LLM provider: `openrouter`, `anthropic`, `mock` |
| `AGENT_LLM_MODEL` | Model ID, e.g. `deepseek/deepseek-v4-pro` |
| `AGENT_LLM_REASONING_EFFORT` | `high`, `medium`, `low` |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `ANTHROPIC_API_KEY` | Anthropic API key (if using Anthropic provider) |

## Deploy to VPS

```bash
VPS_HOST=root@h1.cocode.dk bash scripts/sync-vps.sh
ssh root@h1.cocode.dk 'cd /opt/earn-money && docker compose up -d --build'
```

## Safety boundaries

- **Scope is gospel.** No scan of an asset not in the program's `scope.md`.
- **Two human gates.** Findings queue → verified (operator) → submitted (`bin/submit`).
- **Kill-switch.** `RECON_ENABLED` flag file at repo root.
- **Per-program RoE.** `roe.md` declares technique-level authority per program.
- **Budget gates.** Mission + per-phase budgets bound every agent session.

## Author

**Babak Bandpey** — [cocode.dk](https://cocode.dk) | [LinkedIn](https://linkedin.com/in/babakbandpey) | [GitHub](https://github.com/cocodedk)

## License

Apache-2.0 | © 2026 [Cocode](https://cocode.dk)
