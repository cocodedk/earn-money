# V3 Slice 2 — Forms + Verify Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Playwright-based form interaction (fill_form, submit_form) and the verify phase so the agent can fill forms, submit them, and replay findings for confirmation.

**Architecture:** Two new action dataclasses + driver methods feed through the existing dispatch/observe/emit pipeline. The allowed-action matrix must expose form actions before prompts can advertise them. The verify phase reuses probe actions with a tighter budget and a candidate-existence gate. Form elements are extracted from the accessibility snapshot and grouped by parent form node.

**Tech Stack:** Django, Playwright (async), pytest, asyncio

---

## Frontmatter convention

Every task file under `tasks/` carries a YAML frontmatter block with machine-readable metadata:

- **tier** — `FAST` (Haiku), `CAPABLE` (Sonnet), or `APEX` (Opus)
- **depends_on** — slugs of tasks that must complete first
- **files** — `creates`, `modifies`, `deletes` lists (repo-root-relative paths)
- **exports / imports** — symbols this task provides to or consumes from other tasks
- **allow_extra_files** — whether the agent may touch files not listed

Agents consuming this plan should parse the frontmatter to determine execution order and parallelism.

---

## File structure

See [file-structure.md](file-structure.md) for the full file map.

## Tasks

| # | Task | File |
|---|------|------|
| 1 | FillFormAction and SubmitFormAction dataclasses | [tasks/01-action-dataclasses.md](tasks/01-action-dataclasses.md) |
| 2 | Driver fill() method | [tasks/02-driver-fill.md](tasks/02-driver-fill.md) |
| 3 | Dispatch fill_form and submit_form actions | [tasks/03-dispatch.md](tasks/03-dispatch.md) |
| 4 | Verify phase entry gate | [tasks/04-verify-gate.md](tasks/04-verify-gate.md) |
| 5 | Form grouping in observation builder | [tasks/05-form-extraction.md](tasks/05-form-extraction.md) |
| 6 | Form budget keys and mission profile update | [tasks/06-mission-profile.md](tasks/06-mission-profile.md) |
| 7 | End-to-end controller test | [tasks/07-e2e-test.md](tasks/07-e2e-test.md) |
| 8 | Verify allowed actions and prompt schema snippets | [tasks/08-prompt-verification.md](tasks/08-prompt-verification.md) |

## Execution guardrails

- Complete tasks in order. Task 3 consumes `form_fills` and `form_submits`, so its tests must define those budget ceilings until Task 6 adds them to real mission profiles.
- Treat every code block as a target shape, but match existing local helper names and constructor signatures when the implementation already has an equivalent pattern.
- Roll back task-by-task by reverting the commit created by that task. If a task is still uncommitted, restore only the files listed in that task's **Files** section.
- Do not continue to Task 7 until Tasks 1-6 pass individually; Task 7 is an integration check, not the first place to discover missing wiring.
