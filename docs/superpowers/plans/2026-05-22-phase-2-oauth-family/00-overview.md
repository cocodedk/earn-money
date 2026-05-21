# Phase 2 OAuth/OIDC Family — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement stubs 2.14–2.17 (OAuth/OIDC redirect URI, state missing,
token substitution, account-linking flaws) with the `oauth-lab` fixture.

**Architecture:** One Docker image (`earnmoney-oauth-lab:dev`) built from
`fixtures/oauth-lab/`, exposed as four named compose services differentiated
by `SCENARIO` env var. Python stubs extend the existing skeleton runners in
`backend/apps/stubs/oauth_*`. Design doc:
`docs/superpowers/specs/2026-05-22-oauth-family-design.md`.

**Tech Stack:** Node 22/Express 4 (fixture), Python 3.12/Django (stubs),
pytest/httpx (tests), docker-compose (integration harness).

---

## Task index

| # | Task | Produces |
|---|------|---------|
| 01 | `oauth-lab` fixture — shared infra | `fixtures/oauth-lab/server.js` + `lib/` |
| 02 | Scenario: `state-missing` | `scenarios/state-missing.js` |
| 03 | Scenario: `redirect-uri` | `scenarios/redirect-uri.js` |
| 04 | Scenario: `token-sub` | `scenarios/token-sub.js` |
| 05 | Scenario: `account-link` | `scenarios/account-link.js` |
| 06 | Programs scope+RoE + compose wiring | 4×`programs/local/` + `docker-compose.yml` |
| 07 | Stub 2.15 — oauth-missing-state | `oauth_missing_state/` detection chain |
| 08 | Stub 2.14 — oauth-redirect-uri | `oauth_redirect_uri/` detection chain |
| 09 | Stub 2.16 — oauth-token-substitution | `oauth_token_substitution/` detection chain |
| 10 | Stub 2.17 — oauth-account-linking | `oauth_account_linking/` detection chain |

## After all tasks

Run `/codex-review` (gpt-5.5 xhigh) on the full OAuth family, then
`/code-review high` until clean before marking Phase 2 complete.
