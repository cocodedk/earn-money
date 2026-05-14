# Report Drafting Pipeline — Design Spec

**Date:** 2026-05-15
**Status:** approved
**Phase:** 4 — First Submission Loop

---

## Problem

Findings promoted to `verified` have no draft report. The operator must author
from scratch, which is the bottleneck before any HackerOne submission. Two gaps:

1. No auto-skeleton on promotion to `verified`.
2. No LLM-assisted prose for summary, steps-to-reproduce, and impact sections.

---

## Decision: Approach A — thin wrapper + thin LLM layer

- `transition_state()` stays a pure state-machine primitive (no side effects).
- A new `promote()` wrapper in `triage/verify.py` is the single sanctioned path
  to `verified`; it calls `transition_state()` then `draft_for()`.
- LLM polish is on-demand via `bin/draft --regenerate <hash>`.

Validated by GPT-5.5 consultation: keep `transition_state()` pure; put side
effects in the application layer; expose one higher-level entry point so callers
cannot forget to draft.

---

## New modules

### `src/earn_money/triage/verify.py` (~50 lines)

```
promote(conn, paths, *, platform, slug, finding_hash, actor, note, now)
  → draft_path: Path | None
```

- Calls `transition_state(to_state="verified")`.
- Calls `draft_for()` immediately after.
- If `draft_for()` raises `TemplateNotFound` or `DraftAlreadyExists`, logs a
  warning and returns `None` — the state transition is NOT rolled back.
- Returns the draft path on success.

### `src/earn_money/triage/draft_llm.py` (~90 lines)

```
polish_draft(paths, *, platform, slug, finding_hash, provider)
  → draft_path: Path
```

- Reads the existing skeleton draft from `reports/drafts/<hash>.md`.
- Raises `DraftNotFound` if no skeleton exists (operator must run `bin/draft`
  first without `--regenerate`).
- Sends a single chat completion to `provider`:
  - **System prompt:** act as a senior bug-bounty researcher writing for
    HackerOne; fill in exactly `## Summary`, `## Steps to Reproduce`,
    `## Impact`; leave all other lines unchanged; do not invent steps not
    supported by the evidence block; tone: precise, factual.
  - **User message:** full skeleton draft text + `---EVIDENCE---` separator +
    raw `evidence_block` from the finding row.
  - **Structured output schema:** `{"summary": str, "steps": str, "impact": str}`
- Splices the three fields back into the skeleton by replacing the matching
  `## Section` blocks.
- Writes result with `force=True` (overwrites skeleton).
- Returns the draft path.

---

## `bin/draft` update

Adds `--regenerate` flag:

```
bin/draft --program <slug> --hash <hash> [--regenerate] [--platform <name>]
```

- Without `--regenerate`: existing skeleton behaviour (unchanged).
- With `--regenerate`: calls `polish_draft()`. Requires skeleton to exist.

---

## Wiring changes

| Caller | Change |
|--------|--------|
| `bin/resolve` | Replace `transition_state()` with `promote()` |
| `runners/triage.py` | Replace `transition_state(to_state="verified")` with `promote()` |

No other callers promote to `verified`.

---

## Testing

| File | Covers |
|------|--------|
| `tests/triage/test_verify.py` | `promote()` happy path; template missing → state transitions, draft is None; draft already exists → no crash, returns None |
| `tests/triage/test_draft_llm.py` | Mocked provider: correct system prompt; evidence block in user message; output spliced into correct sections; `DraftNotFound` when skeleton absent |
| Existing `test_draft.py`, `test_history.py` | Must stay green — no changes to those modules |

---

## File sizes

| File | Target lines |
|------|-------------|
| `triage/verify.py` | ~50 |
| `triage/draft_llm.py` | ~90 |
| `bin/draft` (updated) | ~60 |

All under the 200-line cap.

---

## Template prerequisite

`templates/report-draft.md` must contain the three section headers that
`polish_draft` targets:

```
## Summary
## Steps to Reproduce
## Impact
```

The implementation plan includes updating the template before wiring the LLM
layer. Existing placeholder substitution keys (`{{title}}`, `{{asset}}`, etc.)
are unaffected.

---

## Out of scope

- Report submission (`bin/submit`) — already exists in `triage/submit.py`.
- LLM auto-polish on every promotion (Approach C) — rejected; burns credits on
  findings the operator may resolve as NA.
- Multi-platform report templates — current scope is HackerOne only.
