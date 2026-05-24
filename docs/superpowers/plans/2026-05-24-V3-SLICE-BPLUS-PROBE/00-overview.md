# V3 Slice B-plus — Probe Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add click + http_request actions, probe phase, element registry, and evidence contract so the V3 agent can investigate discoveries instead of just finding them.

**Architecture:** Two new action dataclasses + two new driver methods + controller_turn routing for click/http_request + mission profile update to include probe phase + system prompt with new action schemas.

**Tech Stack:** Django, Playwright, httpx (for http_request), dataclasses

**Spec:** `docs/superpowers/specs/2026-05-23-V3-AGENT-ARCHITECTURE/11-slice-b-plus-probe.md`

---

## Key Observations

- Phase-action matrix already allows `click` in enumerate/probe and `http_request` in probe.
- `SLICE_1_PHASES` in controller.py is hardcoded to `["recon", "enumerate", "report"]` — needs to become profile-driven.
- The system prompt template has static action schemas — needs click and http_request added.
- The driver has no `click()` or `http_request()` methods yet.
- `_execute_browser_action` in controller_turn.py only handles navigate — needs click and http_request branches.

## Task Index

1. [Action schemas: ClickAction + HttpRequestAction](01-action-schemas.md)
2. [Driver: click + http_request methods](02-driver-methods.md)
3. [Controller turn: route click + http_request](03-controller-routing.md)
4. [Mission profile: add probe phase + budgets](04-mission-profile.md)
5. [Controller: profile-driven phase list](05-controller-phases.md)
6. [System prompt: add click + http_request schemas](06-system-prompt.md)
7. [Integration: plateau auto-advance through probe](07-integration.md)
