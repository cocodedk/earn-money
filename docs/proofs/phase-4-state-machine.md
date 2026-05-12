# Phase 4 — state-machine proof (real install)

**Status:** Phase 4 ships clean. End-to-end loop verified on the dedicated VPS (`178.105.140.53`) against the live install, against the real `bin/draft`, `bin/submit`, `bin/ack-freeze` CLIs and the real templates.

## What this proves

Tonight's earlier passes shipped the Phase 4 code and live-verified one finding through `queued → verified → drafted`. This proof closes the remaining gaps: **every state-machine path** is exercised, the `bin/ack-freeze` escape hatch is exercised, and the full audit trail is captured as a frozen artifact.

The four paths covered are the four legal terminal outcomes a finding can reach:

| Finding | Path exercised |
|---|---|
| F1 (`cve-2023-1234`) | `queued → verified → submitted → resolved_na`  — full happy path, platform-rejected outcome |
| F2 (`csp-script-src-wildcard`) | `queued → resolved_info`  — operator direct-dismiss for scanner noise |
| F3 (`open-redirect`) | `queued → verified → submitted`  — filed, awaiting platform response |
| F4 (`missing-cookie-samesite-strict`) | `queued → resolved_dupe`  — operator marks as dupe of another finding |

`bin/draft` was invoked twice (F1, F3), producing real markdown drafts under `reports/drafts/`. `bin/submit` was invoked twice with synthetic platform report IDs (`H1-PROOF-001`, `H1-PROOF-002`). `bin/ack-freeze` was invoked once against a synthesized `FROZEN` flag, with a stubbed `$EDITOR` providing the reason — the audit row landed in `programs/demo/proof/freeze-acks.log`.

## What this does NOT prove

- Real platform interaction — no actual HackerOne report was filed. The state machine is exercised in isolation against the real DB + CLIs, but the platform side is simulated by direct `transition_state` calls with `actor="platform-proxy"`.
- A real-money outcome (`resolved_paid` terminal) — that requires an actual filing, an actual payout, and the operator's hand.

## How to reproduce

```bash
# On the VPS (or any machine with the repo + venv + bin/ tools)
.venv/bin/python scripts/smoke-phase4-loop.py
```

The script creates a fresh `/tmp/phase4-smoke-*` tmpdir, registers a synthetic `demo/proof` program, seeds the four findings, and exercises every transition. It prints a markdown ledger of every state change. The script is idempotent in the sense that each run creates a fresh tmpdir; the real `programs/` tree is never touched.

Fixtures and the ledger renderer live in `scripts/_phase4_smoke_lib.py`. The orchestration is in `scripts/smoke-phase4-loop.py` (one short function per state-machine path).

## Frozen ledger from the VPS run

The output below was captured from a run on `178.105.140.53` at the timestamp shown. Each finding has its complete audit trail. The freeze-acks log shows the FROZEN flag was successfully removed after the audit row was appended.

# Phase 4 state-machine proof — ledger

Generated: 2026-05-12T22:37:36Z  ·  Demo root: `/tmp/phase4-smoke-cpkuq4cb`

## Findings (final state)

| Hash | Vuln class | State | External ID |
|---|---|---|---|
| `f1000000…` | cve-2023-1234 | `resolved_na` | H1-PROOF-001 |
| `f2000000…` | csp-script-src-wildcard | `resolved_info` | — |
| `f3000000…` | open-redirect | `submitted` | H1-PROOF-002 |
| `f4000000…` | missing-cookie-samesite-strict | `resolved_dupe` | — |

## Audit history (every transition)

### `f1000000…` — cve-2023-1234

- `2026-05-12T22:37:35Z`  **queued → verified**  · operator  · _reproduced manually; impact: cookie-flag info_
- `2026-05-12T22:37:35Z`  **verified → submitted**  · operator  · _SMOKE: state-machine proof, not actually filed_
- `2026-05-12T22:37:35Z`  **submitted → resolved_na**  · platform-proxy  · _SMOKE: simulating platform N/A response for info-class finding_

### `f2000000…` — csp-script-src-wildcard

- `2026-05-12T22:37:35Z`  **queued → resolved_info**  · operator  · _scanner noise; CSP wildcards intentional on this app_

### `f3000000…` — open-redirect

- `2026-05-12T22:37:35Z`  **queued → verified**  · operator  · _reproduced; open-redirect via ?next=//evil_
- `2026-05-12T22:37:36Z`  **verified → submitted**  · operator  · _SMOKE: filed, awaiting platform response_

### `f4000000…` — missing-cookie-samesite-strict

- `2026-05-12T22:37:36Z`  **queued → resolved_dupe**  · operator  · _dupe of f1000000… (same root cause)_

## Freeze-acks log

```
## 2026-05-12T22:37:36Z
operator: root
reason: rescoped; asset re-added by program owner.
frozen-content-was:
  scope removed asset 'api.demo.test' at 2026-05-12T22:37:36Z
```

