---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 17
spec: 6
slug: content-type-confusion
status: pending     # pending | in-progress | blocked | done
fixture: tbd        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 17.6 Content-type confusion

> Phase 17 — HTTP request/response handling

<!--
GPT-5.5: Enrichment zone — paste-ready spec contract for LLM-assisted implementation.

Goal: enrich this spec so a coding agent can implement it safely and consistently.

PROTECTED — do not modify:
- YAML frontmatter (between `---` fences at top of file).
- Title heading, blockquote breadcrumb, and the `##` section headings.

EDITABLE — fill these:
- The body under each `##` section. Sub-headings (`###`), lists, code blocks, tables welcome.

OUTPUT FORMAT:
- Return raw markdown directly. Do NOT wrap the response in a ` ```markdown ` code fence.
- Inside the body, use exactly 3 backticks for code fences. No 4-backtick blocks.

CONTENT RULES:
- Use shared `ScanTarget` and `Evidence` from ../00-shared-schema.md. Do not redefine them.
- Define only stub-specific `<Name>Signature` and `<Name>Finding` types.
- Detection is deterministic. AI is `None` unless a deterministic gap is named under Safety.
- Pass/fail check has explicit assertions, including negative ones (what must NOT happen).
- Confidence: `low | medium | high`. Finding status: `candidate | confirmed | rejected | stale`.
- Never hard-code hostname → expected tech; detect from response evidence.
- Follow the Coding-agent rules in ../00-shared-schema.md.
-->

## Purpose

<!-- One short paragraph: what this technique detects and why a runner cares. -->

## Inputs

<!-- What the runner receives: target URL, optional credentials, config knobs. -->

## Detection logic

<!-- Deterministic methods only: HTTP methods, headers, body patterns, paths, scanner capabilities. -->

## Persistence

<!-- Use shared `ScanTarget` and `Evidence` from `../00-shared-schema.md`. Define only stub-specific `<Name>Signature` and `<Name>Finding` types here. -->

## Safety

<!-- Read-only vs mutating behavior. HTTP-method discipline. Payload restrictions. PII handling. AI involvement (default: None). -->

## Pass/fail check

<!-- Explicit assertions, including negative ones (what must NOT happen). -->

## Test fixtures

<!-- Which fixture(s) — `juice-shop` / `dvwa` / `webgoat` / new slug — and which feature in the container exposes the bug. -->

## Acceptance criteria

<!-- Operational quality bar: idempotent, completes within budget, handles TLS errors gracefully, no flaky retries. -->
