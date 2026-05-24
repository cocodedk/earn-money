# Phase 3 — Session Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 16 session-management detection stubs (3.1–3.16) across four families, each with 100% TDD coverage and spec-review sign-off.

**Architecture:** Sequential family delivery — A (cookie flags) → B (session lifecycle) → C (JWT/tokens) → D (cross-user). Each family ships its Docker fixture container + stubs as one PR. Shared infrastructure lives in `backend/apps/stubs/_shared/session/`.

**Tech Stack:** Python/Django, httpx, pytest, Node.js (fixtures), Docker Compose.

---

## Families

| Family | Plan file | Stubs | Fixture |
|--------|-----------|-------|---------|
| A — Cookie flags | [family-A-cookie-flags.md](family-A-cookie-flags.md) | 3.1–3.4 | `session-cookie-attributes` (new) |
| B — Session lifecycle | [family-B-session-lifecycle.md](family-B-session-lifecycle.md) | 3.5–3.8 | `session-lifecycle` (new) |
| C — JWT/tokens | [family-C-jwt-tokens.md](family-C-jwt-tokens.md) | 3.9–3.13 | `jwt-session-fixture` (new) |
| D — Cross-user | [family-D-cross-user.md](family-D-cross-user.md) | 3.14–3.16 | TBD per spec |

## Shared infrastructure

All families share:
- `backend/apps/stubs/_shared/session/` — cookie parser, session helpers
- `backend/apps/stubs/_shared/session/tests/` — shared helper tests
- `guarded_runner` decorator from `backend/apps/stubs/runners.py`
- `Evidence`/`Finding`/`ScanRun`/`ScanTargetRun` models (unchanged)

## Branch / PR strategy

| Branch | Contents |
|--------|----------|
| `feat/em-backend-phase-3-cookie-flags` | Family A: fixture + 3.1–3.4 + shared cookie parser |
| `feat/em-backend-phase-3-session-lifecycle` | Family B: fixture + 3.5–3.8 |
| `feat/em-backend-phase-3-jwt-tokens` | Family C: fixture + 3.9–3.13 |
| `feat/em-backend-phase-3-cross-user` | Family D: fixture + 3.14–3.16 |

Each branch stacks on the previous merged tip (stacked-branch convention).
