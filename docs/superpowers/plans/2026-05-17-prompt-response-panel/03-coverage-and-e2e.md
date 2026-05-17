# Verification tasks (V1–V4)

After all backend (B1–B8) and frontend (F1–F9) tasks land, verify 100% coverage on every file touched by this feature, then run the manual smoke + VPS check.

---

## V1: Backend 100% coverage

- [ ] **Run.** `uv run pytest --cov=src/earn_money --cov-report=term-missing tests/agent/test_hacker_loop.py tests/dashboard/test_probe_runner.py tests/dashboard/test_probe_routes.py tests/dashboard/test_probe_static_assets.py`
- [ ] **Expected target files at 100%:**
  - `src/earn_money/agent/hacker_loop.py` — all branches touched by this feature (`_get_llm_response`, the four hooks, `_call_provider_with_rf_fallback`)
  - `src/earn_money/dashboard/probe_runner.py` — all three hook overrides
- [ ] **Process uncovered lines** one at a time: identify branch, add the specific test case that hits it, re-run. Pre-existing uncovered lines (in code NOT touched by this feature) are OUT OF SCOPE; we add them to a separate follow-up issue, not this PR.
- [ ] **Commit** any added tests as `test(probe-panel): close coverage gap on <branch>`.

---

## V2: Frontend 100% coverage

- [ ] **Run.** `node --test --experimental-test-coverage tests/frontend/`. Node 22+ produces an inline coverage table.
- [ ] **Target files at 100%:**
  - `src/earn_money/dashboard/templates/static/probe-status.js`
  - `src/earn_money/dashboard/templates/static/probe-state.js`
  - `src/earn_money/dashboard/templates/static/probe-detail.js`
- [ ] **Process uncovered lines** same as V1. `probe-render.js` and `probe.js` are NOT fully unit-testable from `node --test` (they touch the DOM via `<script>` in browser); the static-asset regex test in F9 + the visual smoke in V3 cover what unit tests can't. Document any unreachable-from-`node` lines with an `/* c8 ignore next */` comment AND a one-line justification.
- [ ] **Commit** added tests as `test(probe-panel): close coverage gap on <function>`.

---

## V3: Local smoke

- [ ] `touch RECON_ENABLED`
- [ ] `uv run python -m earn_money.dashboard.server --root .` (background or separate terminal)
- [ ] Open `http://127.0.0.1:8080/`, switch to Probe tab.
- [ ] Confirm: split layout renders; right panel shows "Waiting for first turn…"; no console errors.
- [ ] Kill server. No commit (smoke only).

---

## V4: Live VPS verification

Follow `consolidated.v6.md § Live VPS check`. Operator-driven (Babak). I cannot do this autonomously — confirm with operator before deploying.

Goal: walk through the 7-step transcript scenario (turn lands, retry, tab switching, selection sticks, follow-latest, restart) on `https://target.cocode.dk`.

- [ ] **Hold for operator confirmation** before deploying. Implementation is "code complete" when V1 + V2 pass; V4 is the integration gate.

---

**Done.** All acceptance criteria from `00-overview.md § Acceptance Criteria` should be satisfied. Open the PR or merge into `main` per `superpowers:finishing-a-development-branch`.
