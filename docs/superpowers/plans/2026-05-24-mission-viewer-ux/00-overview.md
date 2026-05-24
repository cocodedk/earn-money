# Mission Viewer UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire 4 pre-built components + 1 inline change into the mission viewer to show agent intent, outcomes, discoveries, structured observations, and budget bars.

**Architecture:** Components `BudgetBars`, `OutcomeDigest`, `DiscoveryChips`, `ObservationDetails` already exist with full implementations and CSS modules. This plan writes tests for each, wires them into TurnCard/StoryTimeline/MissionStrip, and updates existing tests.

**Tech Stack:** React, TypeScript, Vitest, CSS Modules with design tokens

---

## Tasks

| Task | File | Description |
|------|------|-------------|
| 1 | [tasks/01-intent-lines.md](tasks/01-intent-lines.md) | Add reason + hypothesis lines to TurnCard |
| 2 | [tasks/02-outcome-digest.md](tasks/02-outcome-digest.md) | Test OutcomeDigest + wire into TurnCard |
| 3 | [tasks/03-observation-details.md](tasks/03-observation-details.md) | Test ObservationDetails + wire into TurnCard details panel |
| 4 | [tasks/04-discovery-chips.md](tasks/04-discovery-chips.md) | Test DiscoveryChips + wire into StoryTimeline |
| 5 | [tasks/05-budget-bars.md](tasks/05-budget-bars.md) | Test BudgetBars + wire into MissionStrip |
| 6 | [tasks/06-final-verify.md](tasks/06-final-verify.md) | Full suite run + type check + commit |

## Dependencies

Tasks 1-5 are independent — they modify different components. Task 6 depends on all.
