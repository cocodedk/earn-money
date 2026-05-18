---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# seven lines intact. Values below the comments are yours to change.
phase: 7
spec: 3
slug: token-not-tied-to-session
spec_file: docs/superpowers/specs/2026-05-18-VULN-SCANNING-COOK-BOOK/07-csrf-and-browser-side-request-abuse/03-token-not-tied-to-session.md
status: pending           # pending | drafted | approved | implemented | verified
implementation_file: null
test_file: null
---

# Plan: 7.3 Token not tied to session

> Spec: [`07-csrf-and-browser-side-request-abuse/03-token-not-tied-to-session.md`](../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/07-csrf-and-browser-side-request-abuse/03-token-not-tied-to-session.md)

<!--
Planner / GPT-5.5: Enrichment zone — paste-ready plan contract for LLM-assisted implementation.

Goal: draft a plan a coding agent can execute step-by-step against the linked spec.

PROTECTED — do not modify:
- YAML frontmatter (between `---` fences at top of file).
- Title heading, Spec-reference blockquote, `##` section headings.

EDITABLE — fill these:
- The body under each `##` section.

OUTPUT FORMAT:
- Return raw markdown directly. No ` ```markdown ` wrapper. 3-backtick fences only.

CONTENT RULES:
- TDD steps must be numbered. Each step = (test name → minimal impl → commit message).
- File paths under `## Files to touch` are exact, distinguished as "create" vs "modify".
- `## Persistence wiring` references shared `ScanTarget` / `Evidence` from
  ../../../specs/2026-05-18-VULN-SCANNING-COOK-BOOK/00-shared-schema.md — do not redefine.
-->

## Summary

<!-- One short paragraph: what this plan ships. -->

## Files to touch

<!-- Exact paths to create / modify (runner, test, schema, CLI). -->

## TDD steps

<!-- Numbered: failing test → minimal impl → green → refactor → commit. -->

## Verification

<!-- How we prove the implementation works against the fixture, end-to-end. -->

## Persistence wiring

<!-- How findings from this runner are written into the backend. -->
