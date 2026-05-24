# Mission Viewer Backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add REST endpoints, a Celery task, and SSE enrichment so the frontend mission viewer can start, stream, and inspect V3 agent sessions.

**Architecture:** Three new files in `backend/apps/agent/` (serializers, views, tasks) plus modifications to event_log, controller_turn, SSE views, event types, requirements, and Dockerfile. Follows existing DRF/Celery/SSE patterns exactly.

**Tech Stack:** Django REST Framework, Celery, Redis, Playwright, SSE via StreamingHttpResponse

**Spec:** `docs/superpowers/specs/2026-05-23-MISSION-VIEWER-BACKEND/`

---

## Execution Guardrails

- Implement tasks in order unless a task file explicitly names a dependency exception.
- Do not deploy or manually exercise the POST start-mission endpoint after Task 5 until Task 8 is also complete; Task 5 adds the enqueue hook and Task 8 provides the task implementation.
- After each task, run the task-local tests before committing and do not carry a red test suite into the next task.
- Rollback is per task commit: revert the latest task commit, rerun the tests named in that task, and only then continue. If no commit was made yet, undo only the files listed in that task's **Files:** block.
- If a migration is generated in Task 1, include it in the same task commit and roll it back with that commit.

---

## Task Index

1. [Add SCAN_RUN_FAILED event type](01-event-type.md)
2. [SSE generic frames — drop event: line](02-sse-generic-frames.md)
3. Agent serializers (split):
   - [3A: Observation, Action, Note](03-serializers-observation-action-note.md)
   - [3B: Turn + Session](03-serializers-turn-session.md)
4. Agent viewset read (split):
   - [4A: List + Detail](04-viewset-read-list-detail.md)
   - [4B: Turns, Notes, Read-Only](04-viewset-read-turns-notes.md)
5. Agent viewset create (split):
   - [5A: Success path](05-viewset-create-success.md)
   - [5B: Serializer write logic](05-viewset-create-serializer.md)
   - [5C: Validation tests](05-viewset-create-validation.md)
6. Event enrichment (split):
   - [6A: Helpers](06-event-enrichment-helpers.md)
   - [6B: Emitter signatures](06-event-enrichment-emitters.md)
7. [Controller turn — persist consumed_budget](07-budget-persist.md)
8. Celery task (split):
   - [8A: Success path](08-celery-task-impl.md)
   - [8B: Full implementation code](08-celery-task-code.md)
   - [8C: Stopped, failed, idempotent](08-celery-task-edge-cases.md)
9. [URL registration](09-url-registration.md)
10. [Runtime dependencies](10-runtime-deps.md)
