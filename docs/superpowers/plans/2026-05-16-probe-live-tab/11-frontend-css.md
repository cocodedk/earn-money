# Task 11 — `probe.css`

**Spec section:** `docs/superpowers/specs/2026-05-16-probe-live-tab/10-frontend-css.md`

**Files:**
- Create: `src/earn_money/dashboard/templates/static/probe.css`
- Optionally modify: `src/earn_money/dashboard/templates/static/tokens.css` (only if `--text-muted` or `--border` aren't already defined)

The CSS file styles the tabs, the launcher form, the timeline turn cards, the finding rows, the terminal banners, and the hint text. Reuses the existing design tokens from `tokens.css`.

- [ ] **Step 1: Check which tokens are already in `tokens.css`**

```bash
grep -E '^\s*--(text-muted|border|accent|surface|surface-2|ok|warn|mono)\s*:' src/earn_money/dashboard/templates/static/tokens.css
```

- [ ] **Step 2: Add missing tokens (only if Step 1 shows any of `--text-muted` or `--border` are absent)**

Append the missing definitions inside the existing `:root { … }` block of `tokens.css`. Use the existing palette — match whatever the surrounding tokens look like (likely light-on-dark or dark-on-light depending on `color-scheme`). If unsure, copy values from a sibling project's `tokens.css` rather than inventing.

- [ ] **Step 3: Create `probe.css`**

Create `src/earn_money/dashboard/templates/static/probe.css` with the spec's exact content:

```css
/* tabs */
.tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.tab  {
  padding: 0.5rem 1rem;
  border: 1px solid var(--border);
  background: var(--surface);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.9rem;
}
.tab.active {
  background: var(--surface-2);
  border-bottom-color: transparent;
  font-weight: 600;
}

/* probe form */
#probe-launcher form {
  display: grid;
  gap: 0.5rem;
  grid-template-columns: repeat(2, 1fr);
}
#probe-launcher label {
  display: flex;
  flex-direction: column;
  font-size: 0.85rem;
  gap: 0.25rem;
}
#probe-launcher input {
  font-family: var(--mono);
  padding: 0.4rem;
  border: 1px solid var(--border);
  background: var(--surface);
}
#probe-launcher .hint {
  color: var(--text-muted);
  font-size: 0.75rem;
}
#probe-launcher button {
  grid-column: 1 / -1;
  padding: 0.6rem;
  font-family: var(--mono);
  font-size: 0.9rem;
  cursor: pointer;
}
#probe-launcher button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* timeline / turn cards */
#probe-timeline {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 1rem;
}
.turn-card {
  border-left: 3px solid var(--accent);
  padding: 0.5rem 0.75rem;
  background: var(--surface);
}
.turn-card header {
  display: flex;
  gap: 1rem;
  font-family: var(--mono);
  font-size: 0.85rem;
  align-items: baseline;
}
.turn-num    { font-weight: 700; }
.model-id    { color: var(--text-muted); }
.tokens      { color: var(--text-muted); }

.slot {
  font-family: var(--mono);
  font-size: 0.85rem;
  white-space: pre-wrap;
  margin-top: 0.25rem;
  word-break: break-word;
}
.slot-action[data-recovered="true"]::before {
  content: "⚠ recovered  ";
  color: var(--warn);
}
.slot-policy.policy-ok   { color: var(--ok); }
.slot-policy.policy-deny { color: var(--warn); }

.turn-card.complete       { opacity: 0.95; }
.turn-card.outcome-denied { border-left-color: var(--warn); }

/* findings */
.finding-row {
  background: var(--surface-2);
  padding: 0.25rem 0.5rem;
  margin-top: 0.25rem;
  font-family: var(--mono);
  font-size: 0.8rem;
}
.finding-verified { border-left: 2px solid var(--warn); }

/* terminal banners */
.timeline-banner {
  padding: 0.5rem;
  font-family: var(--mono);
  background: var(--surface-2);
  border-radius: 2px;
}
.timeline-banner.error { color: var(--warn); }
```

- [ ] **Step 4: Verify file size**

```bash
wc -l src/earn_money/dashboard/templates/static/probe.css
```

Expected: ≤150 lines.

- [ ] **Step 5: Existing server tests still pass**

```bash
uv run pytest tests/dashboard/ -q
```

- [ ] **Step 6: Manual smoke (optional)**

```bash
uv run python -m earn_money.dashboard.server --root . &
SERVER_PID=$!
sleep 1
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://127.0.0.1:8080/static/probe.css
kill $SERVER_PID
```

Expected: `200 text/css; charset=utf-8`.

- [ ] **Step 7: Commit**

```bash
git add src/earn_money/dashboard/templates/static/probe.css \
        src/earn_money/dashboard/templates/static/tokens.css  # only if step 2 modified it
git commit -m "feat(dashboard): probe.css timeline + turn-card styles"
```
