# Task 12 — `.env.example` entry + final test/lint pass

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/03-task-routing.md` §5; plus full-suite verification.

**Files:**
- Modify: `.env.example` (or create if absent)

This is the closing task: the one missing config entry and a full test+lint sweep before declaring the feature done. Per pre-flight (overview.md), `.env.example` may not exist in this repo — create-or-append.

- [ ] **Step 1: Check whether `.env.example` exists**

```bash
ls -la .env.example 2>/dev/null && echo "exists" || echo "absent"
```

- [ ] **Step 2: Add the AGENT_PLANNING entry**

If `.env.example` exists, append:

```bash
cat >> .env.example <<'EOF'

# Probe loop per-turn model selection (optional — falls back to OPENROUTER_DEFAULT_MODEL)
OPENROUTER_MODEL_AGENT_PLANNING=
EOF
```

If `.env.example` does **not** exist, create it with just the new line and a tiny header:

```bash
cat > .env.example <<'EOF'
# Example environment variables for earn-money.
# Copy to .env and fill in real values; never commit .env (gitignored).

# Probe loop per-turn model selection (optional — falls back to OPENROUTER_DEFAULT_MODEL)
OPENROUTER_MODEL_AGENT_PLANNING=
EOF
```

Do **not** copy keys or other entries from `.env` — that file contains secrets and the spec was explicit about not propagating them.

- [ ] **Step 3: Run the full test suite**

```bash
uv run pytest -q
```

Expected: all tests pass, including the new ones from Tasks 1–11. The starting test count was ~795 (pre-feature); the new total should be ~795 + the count of new tests added across:
- `tests/agent/test_task_router.py` (+3)
- `tests/agent/test_probe_actions.py` (+~7 across `TestParseActionRecovery` + `TestParseActionBackwardCompat`)
- `tests/agent/test_hacker_loop.py` (+2 to 3 — `TestHooks`, `TestResponseFormatPassthrough`)
- `tests/dashboard/test_probe_runner.py` (new file, ~30 tests per spec 12)
- `tests/dashboard/test_probe_routes.py` (new file, ~30 tests per spec 12)

Final count somewhere around 870. If a test fails, fix the underlying task before this one — do not paper over with skips.

- [ ] **Step 4: Run lint across all touched paths**

```bash
uv run ruff check \
  src/earn_money/agent/ \
  src/earn_money/dashboard/ \
  tests/agent/ \
  tests/dashboard/
```

Expected: clean. Fix any ruff complaints surgically (no broad reformatting).

- [ ] **Step 5: Skim every file the plan touched and ask if any one feels tangled**

```bash
wc -l \
  src/earn_money/agent/task_router.py \
  src/earn_money/agent/probe_actions.py \
  src/earn_money/agent/hacker_loop.py \
  src/earn_money/dashboard/probe_runner.py \
  src/earn_money/dashboard/server.py \
  src/earn_money/dashboard/templates/index.html \
  src/earn_money/dashboard/templates/static/tabs.js \
  src/earn_money/dashboard/templates/static/probe.js \
  src/earn_money/dashboard/templates/static/probe-render.js \
  src/earn_money/dashboard/templates/static/probe.css \
  tests/dashboard/test_probe_runner.py \
  tests/dashboard/test_probe_routes.py
```

No fixed cap — line count is informational. The question is whether any single file mixes responsibilities or has grown harder to reason about than its individual pieces. If yes, split for readability (the spec already calls out logical seams, e.g. `probe_runner_events.py`, `probe_runner_select.py`, `probe-stream.js`). If no, leave them.

- [ ] **Step 6: Manual smoke against a local target (optional)**

```bash
touch RECON_ENABLED
EARN_MONEY_LLM_PROVIDER=openrouter \
OPENROUTER_DEFAULT_MODEL=qwen/qwen3-235b-a22b:free \
uv run python -m earn_money.dashboard.server --root .
```

Open `http://127.0.0.1:8080/` in a browser, click PROBE, fill `base_url=http://target.cocode.dk`, `roe_profile=roe/local-lab.yaml`, `max_turns=5`, click RUN. Watch the timeline render turn cards live. Confirm:
- Tab state persists across page refresh (`#tab=probe` in URL).
- `Cmd-F` finds text in turn cards.
- Removing `RECON_ENABLED` and clicking RUN shows the gate error banner.
- A second RUN while the first is running shows the 409 conflict banner.

- [ ] **Step 7: Commit and confirm clean working tree**

```bash
git add .env.example
git commit -m "chore(env): document OPENROUTER_MODEL_AGENT_PLANNING"
git status
```

Expected: `nothing to commit, working tree clean`.

- [ ] **Step 8: Branch summary**

```bash
git log --oneline origin/main..HEAD
```

Expected: 12 commits, one per Task, all using Conventional Commits prefixes (`feat:` / `chore:`).

## Done

The PROBE tab now ships:
- Live SSE streaming of each `HackerLoop` turn, stage by stage.
- Per-turn task selection (`agent_planning`, `coding_security`, `structured_extraction`).
- Defensive action parsing with markdown-fence recovery.
- Full gate / scope / budget enforcement matching the CLI.
- `textContent`-only rendering, `location.hash` tab state, `run_id`-scoped streams, single-active-probe guard.
- Readable file boundaries; split only when responsibilities become mixed.

Hand the branch to the operator for review and merge.
