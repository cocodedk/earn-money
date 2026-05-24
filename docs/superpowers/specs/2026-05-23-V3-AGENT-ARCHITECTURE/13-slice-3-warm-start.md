---
slug: slice-3-warm-start
status: draft
---

# Slice 3 — Warm-Start Target Memory

Slice 2 proved form interaction and the verify phase. Slice 3 adds **target memory** — when a
mission runs against a previously-probed target, the agent starts with compact prior intel that
accelerates exploration without fabricating evidence.

## Core invariant

Prior intel may influence exploration priority, but only current-session observations and
current-session `submit_candidate` calls can satisfy verification.

## Goal

After Slice 3, the agent can:

1. Receive a compact summary of what prior missions discovered (routes, forms, candidates, gaps).
2. Treat prior candidates as re-check targets — hypotheses to test, not existing findings.
3. Skip already-mapped routes in plateau scoring, pushing toward unexplored areas.
4. Omit the intel section entirely when no prior session exists.

## Part 1 — Prior intel in the system prompt

When a previous completed session exists for the same target, inject a new section into the
system prompt after the phase section:

```
## Prior Target Intel

Source session: <session_id>, completed at <date>
Freshness: <fresh | stale — treat with lower confidence>

These are unverified hints from a previous session. You must re-observe
to get current element IDs. Prior candidates are re-check targets, not
current evidence.

Known routes:
  /#!/score-board
  /#!/login
  /api/Challenges

Known forms:
  POST /rest/user/login — email, password
  POST /api/Users — email, password, passwordRepeat, securityQuestion, securityAnswer

Prior candidates to re-check:
  - category: exposure
    description: hidden scoreboard at /#!/score-board
    status: re-check
    instruction: re-verify in current session

Gaps / hypotheses:
  - chatbot requires Ollama integration
  - web3 challenges need Sepolia ETH
```

The section includes:

- **Known routes** discovered previously. Hash-based SPA routes like `/#!/score-board` are
  preserved — they represent meaningful application states, not noise. Route normalization
  removes obvious duplication but does not erase app navigation state.
- **Known forms** by stable signature: action URL + method + normalized input names.
- **Prior candidates** as re-check targets with category, description, and explicit instruction
  to re-verify in the current session.
- **Gaps and hypotheses** from prior session notes.

## Part 2 — Plateau baseline

PlateauDetector gets an optional constructor argument:

```python
known_routes: set[str] | None = None
```

Routes already in this baseline do not count as new discoveries in `record_turn()`. This pushes
the agent past already-mapped areas faster without pretending those areas were observed.

Important nuance: revisiting a known route can still matter if the agent finds new forms, changed
UI, new state, auth-gated behavior, or fresh candidate evidence. Only the novelty scoring is
affected, not the agent's ability to act on known routes.

## Part 3 — Prior candidate re-check list

Prior candidates are injected as a structured list in the prompt. The agent treats them as test
targets:

- They can influence navigation priority.
- They can suggest what to inspect.
- They cannot satisfy verification.
- They cannot be reported as current findings unless rediscovered and submitted in the current
  session.

The verify gate remains unchanged: only a fresh `submit_candidate` from the current session can
produce a verified finding.

## Data flow

New module: `backend/apps/agent/target_intel.py`

```python
@dataclass
class FormSignature:
    action: str
    method: str
    input_names: list[str]

@dataclass
class PriorCandidate:
    category: str
    description: str

@dataclass
class TargetIntel:
    source_session_id: str
    source_completed_at: datetime
    is_stale: bool
    known_routes: set[str]
    form_signatures: list[FormSignature]
    prior_candidates: list[PriorCandidate]
    hypotheses: list[str]
```

Builder function:

```python
def build_target_intel(
    target: ScanTarget,
    prior_session: AgentSession | None,
    *,
    stale_after_days: int = 7,
    max_routes: int = 20,
    max_forms: int = 10,
    max_candidates: int = 10,
    max_notes: int = 5,
) -> TargetIntel | None:
```

Returns `None` when no prior session exists. The serialized prompt section is deterministic and
capped to roughly 200-300 tokens. One noisy prior session cannot bloat the system prompt.

## Task flow

1. Celery task finds the most recent completed session for the same target.
2. `build_target_intel()` extracts routes, form signatures, candidates, and notes.
3. `MissionController` passes the intel to `build_system_prompt()`.
4. `build_system_prompt()` includes `## Prior Target Intel` only when intel exists.
5. `PlateauDetector` receives `target_intel.known_routes` as its baseline.

If no prior session exists, the entire section is omitted and plateau starts fresh.

## Staleness

The source session date is included in the prompt. If the prior session is older than the
configured threshold (default: 7 days), the prompt labels it:

```
Freshness: stale — treat with lower confidence
```

Configurable on the mission profile. Stale intel can still be useful for route seeds, but
hypotheses and candidates are treated cautiously.

## Identity rules

"Same target" is strict. Match by configured target ID (ScanTarget primary key), not by loose URL
similarity. Target identity accounts for host, scheme, and environment boundaries. Bad carryover
is worse than no carryover.

## Out of scope

- Cross-target intel sharing (e.g., applying Juice Shop knowledge to a different Juice Shop
  instance).
- Multi-session aggregation (only the most recent completed session is used).
- Warm-starting the observation builder's element ID counters (IDs are always current-session).
- Injecting synthetic observations into the message list (option A — explicitly rejected).

## Test strategy

1. No prior session → no prompt section, no baseline routes.
2. Prior session → compact `TargetIntel` with routes, forms, candidates, hypotheses.
3. Stale sessions labeled correctly based on threshold.
4. Hash routes (e.g., `/#!/score-board`) preserved in known routes.
5. Known routes passed into PlateauDetector baseline.
6. Baseline routes do not count as new discoveries in `record_turn()`.
7. Prior candidates appear as re-check targets in prompt.
8. Prior candidates cannot satisfy verify gate without fresh `submit_candidate`.
9. Serialization is deterministic and capped at token limit.
10. Missing/empty prior session fields handled gracefully.
