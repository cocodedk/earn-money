# 10 — Frontend · CSS

One new file: `src/earn_money/dashboard/templates/static/probe.css`. Target ≤120 lines. Reuses design tokens from the existing `tokens.css`.

## Reused tokens

From `templates/static/tokens.css` (existing, 31 lines):
- `--accent` — primary line / divider colour
- `--surface` — card background
- `--surface-2` — finding row background, active tab background
- `--ok` — green success colour
- `--warn` — red/amber warning colour
- `--mono` — monospace font family
- `--border` — border colour for cards / tabs
- `--text-muted` — secondary text colour (model id, token estimate)

If `--text-muted` or `--border` aren't already defined in `tokens.css`, add them in this PR — a 1- or 2-line addition to a 31-line file keeps `tokens.css` well under any code cap.

## `probe.css`

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

## Why no animation

The original PROBE-LIVE-TAB.md and the REVISED both stay animation-free. SSE updates are already perceptibly "live" — DOM mutations from a stream feel responsive without easing. Adding fades or slides increases CPU work on long-running probes (50+ cards) for no information gain.

If a card-entry animation is wanted later, the cleanest add is:

```css
@keyframes turn-enter {
  from { opacity: 0; transform: translateY(-2px); }
  to   { opacity: 1; transform: translateY(0); }
}
.turn-card { animation: turn-enter 0.15s ease-out; }
```

Two extra rules, no JS change.

## Why no responsive breakpoints

The dashboard is single-operator, desktop-first. The existing `dashboard.css` (192 lines) has no media queries; this file matches that. A future mobile pass would add a breakpoint at ~700px collapsing the form's `grid-template-columns: repeat(2, 1fr)` to `1fr` — trivial to add when needed.

## Accessibility — colour pairings

Every coloured signal is paired with text or a glyph so the meaning survives monochrome rendering or colour-blind viewers:

| Visual signal              | Pairing                              |
|----------------------------|--------------------------------------|
| Green policy text          | ✓ glyph before the reason            |
| Red policy text            | ✗ glyph before the reason            |
| Warn-coloured recovered    | "⚠ recovered" text in the `::before` |
| Warn-coloured outcome bar  | `outcome=denied` class + outcome glyph optional |
| Error banner colour        | "error · " prefix in the text        |

No information is conveyed by colour alone.

## What's NOT here

- Dark/light theme switching beyond what `tokens.css` already provides (`color-scheme: light dark` in `index.html` is enough).
- Custom fonts (uses inherited / token-defined `--mono` only).
- Print styles. The dashboard is a screen-only tool.
