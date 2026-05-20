# Agent spec compliance — implementation plan

Maps `docs/superpowers/specs/2026-05-14-AGENT-design.md` to ship-able PRs.

## Ship order

| PR | Theme | Spec sections | Files (new) |
|----|-------|---------------|-------------|
| **A** | Security core | §6, §7, §8, §9, §10 (full), §12 | `evidence.py`, `injection_detector.py`, `policy_prompt.py`, `action_allowlist.py` |
| **B** | Routing | §2 (headers), §3, §4 | extend `providers.py` + new `task_router.py` |
| **C** | Structured outputs | §5, §11 | `structured.py`, `schemas.py` |
| **D** | Audit + docs | §13, §15 | extend `decider.py` logging + `docs/agent/README.md` |

## Already done (PR #12)

- §1 Provider abstraction — `Provider` protocol + 4 adapters
- §2 OpenRouter base — `OpenAIProvider` with `base_url=https://openrouter.ai/api/v1`
- §10 Proposals safety (partial) — slug whitelist, language whitelist, non-exec bit
- §16, §18 Hard boundaries — orchestrator validates every agent reply

## PR A scope (this branch)

New modules:
- `src/earn_money/agent/evidence.py` — wrap content in `<UNTRUSTED_SCANNED_EVIDENCE>` blocks with metadata. Strip invisible chars; truncate; hash; collect source URL / content type / timestamp.
- `src/earn_money/agent/injection_detector.py` — deterministic detector over ~30 known patterns (ignore previous, you are now, reveal prompt, send data to, base64 blobs, HTML comments, hidden CSS, …). Returns `list[str]` of matched indicators.
- `src/earn_money/agent/policy_prompt.py` — the cybersecurity/GRC trusted-instruction block from spec §6. Re-used by the decider + future structured-output paths.
- `src/earn_money/agent/action_allowlist.py` — typed action policy. Maps `action_type → AllowedRisk` and produces the `proposed_actions[]` validation pass (spec §10 + §11 schema field).

Integration with existing `decider.py`:
- Hostile evidence (recon outputs, scanned HTML, etc.) gets wrapped before being put in the user message.
- Injection-detector results land in the state snapshot so the model sees `injection_suspected=true` indicators.
- The decider response's `proposed_actions` (when present) flow through `action_allowlist.validate(...)` before persistence.
- `requires_human_review` triggers per §12.

Tests:
- evidence wrap round-trip + truncation + hash determinism
- injection detector hits every named pattern in spec §8
- action allowlist rejects everything outside the §10 low-risk list
- decider integration: untrusted-content sample is wrapped + detector flags it

Out of scope for PR A (will land in B/C/D):
- Model profile env vars + task router (PR B)
- Structured JSON-schema response_format (PR C)
- Scanner-analysis schema with full fields (PR C)
- Audit log writer for evidence_id → finding_id chain (PR D)
- The README in `docs/agent/` (PR D)
