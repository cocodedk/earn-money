# Mission Viewer Backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add REST endpoints, a Celery task, and SSE enrichment so the frontend mission viewer can start, stream, and inspect V3 agent sessions.

**Architecture:** Three new files in `backend/apps/agent/` (serializers, views, tasks) plus modifications to event_log, controller_turn, SSE views, event types, requirements, and Dockerfile. Follows existing DRF/Celery/SSE patterns exactly.

**Tech Stack:** Django REST Framework, Celery, Redis, Playwright, SSE via StreamingHttpResponse

**Spec:** `docs/superpowers/specs/2026-05-23-MISSION-VIEWER-BACKEND/`

---

## Task Index

1. [Add SCAN_RUN_FAILED event type](01-event-type.md)
2. [SSE generic frames — drop event: line](02-sse-generic-frames.md)
3. [Agent serializers](03-serializers.md)
4. [Agent viewset — list, retrieve, turns, notes](04-viewset-read.md)
5. [Agent viewset — create (start mission)](05-viewset-create.md)
6. [Event enrichment — budget snapshot + observation summary](06-event-enrichment.md)
7. [Controller turn — persist consumed_budget every turn](07-budget-persist.md)
8. [Celery task — run_agent_session with lifecycle](08-celery-task.md)
9. [URL registration](09-url-registration.md)
10. [Runtime dependencies](10-runtime-deps.md)
