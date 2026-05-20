# Dark mode — Operator Console aesthetic

**Goal:** Eye-friendly dark theme overlay on the existing Operator Console token system. Warm dark base (not pure black, no purple). Amber accent retained. Operator can opt in via toggle; respects system preference by default. Light mode remains unchanged.

**Scope:** Token-system addition + theme-bridge mechanism + 1 toggle UI control + `dark:` variants on the 3 feature-level StatusBadge palettes (Option A — see Components section). 497/497 existing vitest stays green unless exact class-string expectations require mechanical updates; new tests for the toggle + theme bridge bring the suite higher.

## Plan map

- Theme bridge contract, no-FOUC script, store subscription: [01-theme-bridge.md](./01-theme-bridge.md)
- Execution order, test matrix, rollback, hidden dependencies: [02-execution-plan.md](./02-execution-plan.md)
- React-side consumption (toggle + Settings row): [03-react-usage.md](./03-react-usage.md)

## Aesthetic direction

Mirror the light-mode "warm off-white" with a "warm near-black": dark warm-gray (`#14130f`) not pure `#000000`. Pulls slight amber undertone so the accent feels integrated. No purple anywhere.

Ink hierarchy inverts: cream-white strong ink (`#f0ede4`) -> soft warm-gray muted (`#9a948a`) -> softer still (`#6b665d`). Rule hairlines softened to `#2a2823` (visible, not loud).

Status colors lighten for **WCAG AA contrast (>=4.5:1 text, >=3:1 non-text) against the dark canvas**:
- ok: `#4ade80` (was `#1f6e3a`)
- warn: `#fbbf24` (was `#a16207`)
- err: `#f87171` (was `#991b1b`)
- info: `#93bbfc` (was `#1e3a8a`)
- accent: `#f59e0b` (amber-500, was `#b45309` amber-700)

## Mechanism

Two layers, in order:

1. **System default:** `@media (prefers-color-scheme: dark)` block redefines tokens at `:root:not([data-theme="light"])` (excludes a forced-light user). Users with OS dark mode see dark tokens with zero React.
2. **Manual override:** `<html data-theme="dark">` or `<html data-theme="light">` overrides the system pref. Stored in `localStorage` under key `theme`. Set before React mounts via inline script in `index.html` to avoid FOUC.

Tailwind's `dark:` variants use a separate `.dark` class. The bridge must keep `<html class="dark">` in sync with the resolved theme for **both** manual dark and system dark. Two writers update both attributes:

1. **Inline `<script>` in `index.html` `<head>`** (before React) — runs at every page load. Sets `data-theme` AND toggles `.dark` based on stored value (or `matchMedia` if no override). Wrapped in try/catch around `localStorage` + `matchMedia` so blocked-storage / missing-API browsers fall through cleanly. Full script in [01-theme-bridge.md §No-FOUC inline script](./01-theme-bridge.md).
2. **`applyTheme()` in `frontend/src/app/theme.ts`** — called once on React mount via an import-time side effect in `main.tsx` (covers the edge case where storage changed between inline-script run and React mount), and called again from `setTheme()`. Sets both `data-theme` AND `.dark` identically to the inline script. Same guards.

`setTheme()` also dispatches a custom `window` event `themechange`. `subscribeTheme()` listens to three sources: `themechange` (this-tab manual toggle), `storage` (other-tab toggle via localStorage), and `matchMedia` `change` (OS-pref flip). `ThemeToggle` consumes via `useSyncExternalStore(subscribeTheme, getThemeSnapshot)` — all subscribers re-render in lockstep. See [01-theme-bridge.md §Subscription contract](./01-theme-bridge.md).

All `localStorage.{getItem,setItem,removeItem}` and `window.matchMedia` calls in `theme.ts` are wrapped in try/catch; failures fall back to `"system"` resolved against `prefers-color-scheme`. Tests stub `matchMedia` where dark resolution matters; the JSDOM fallback is documented in 01.

**Precedence (explicit cascade):**

```text
1. <html data-theme="light"> -> @media block's :not() excludes it -> light tokens win
2. <html data-theme="dark">  -> :root[data-theme="dark"] block wins over @media's
                              :root:not([data-theme="light"]) by source order:
                              the manual override block sits after the @media block
3. neither attribute set      -> @media follows OS preference
```

Three persisted theme states:
- `"light"` -> `data-theme="light"`, `.dark` removed
- `"dark"` -> `data-theme="dark"`, `.dark` added
- absent/invalid -> follow system, no `data-theme`, `.dark` reflects `matchMedia`

## Toggle UI

Single 3-state cycle button in the topbar (next to `<ConnectionPill>`):
- `data-testid="theme-toggle"`.
- Accessible name includes current and next state, for example `aria-label="Theme: dark; switch to system"`.
- Glyph cycles: sun (light) -> moon (dark) -> monitor (system) -> sun.
- Activation order: light -> dark -> system -> light.
- Settings page §System status grows a row: `<MetaRow label="Theme">{current} (resolved: {resolved})</MetaRow>`.

## Components that need attention

The token system already covers every **primitive in `components/`** — `Button`, `Callout`, `EmptyState`, `Form`, `MetaList`, `PageHeader`, `Table`, `ConnectionPill`, `CurrentProjectChip` adapt automatically when tokens flip.

**Hardcoded Tailwind colours to migrate — 14 files** (audit via `rg -n '(text|bg|border)-(gray|blue|green|amber|red|yellow|orange)-|bg-white|border-white' frontend/src/ --type-add 'web:*.{tsx,ts,css}' -tweb -g '!*.test.*' -g '!*StatusBadge*'` — explicitly excludes tests AND the `StatusBadge` files because they're handled via Tailwind `dark:` companions in step 2, not the token migration):

1. `app/Layout.module.css` — sidebar `bg-gray-50 border-gray-200`, nav `text-gray-700 hover:bg-gray-100`, topbar `border-gray-200 bg-white`, brand `text-gray-900` → tokens.
2. `features/settings/Settings.tsx` — `<BoolBadge>` + `<StatusBadge>` `text-{gray-500,green-700,red-700,amber-700}` → token styles.
3-7. `features/{targets,scan-runs,findings,evidence,stubs}/*FiltersBar.tsx` (5 files) — `text-gray-600` label inside `<span>` inside `<label>` → `style={{ color: "var(--ink-muted)" }}`.
8. `features/projects/ProjectPickerField.tsx:42` — `border-gray-300` on `<select>` → `var(--rule-soft)`.
9. `features/scan-runs/CreateScanRun.tsx` (lines 150, 170, 195) — `border-gray-300` + `text-gray-600` → token styles.
10. `features/scan-runs/EventsPanelHeader.tsx` (lines 4-9) — STATUS_CLASS map with `bg-{amber,green,blue,gray,red}-100 text-...-800` for each connection status → add `dark:` variants OR refactor to a token-driven `data-status` attribute selector in a sibling `.module.css`. Recommend the latter — same pattern as the design-polish StatusBadge migration.
11. `features/scan-runs/ScanRunLiveEventsPanel.tsx` (lines 22-25) — LEVEL_CLASS map with `text-{gray,blue,amber,red}-600 bg-...-100` for event levels → same approach as item 10.
12. `features/scan-runs/LifecycleActions.tsx:14` — `bg-gray-200 hover:bg-gray-300` on a `<button>` → `var(--surface-sunken)` + `hover:bg-[var(--surface-canvas)]`.
13. `features/stubs/StubDetail.tsx:28` — `bg-gray-50 border-gray-200` on a `<pre>` code block → `var(--surface-sunken)` + `var(--rule-hair)`.

14. `frontend/src/features/coming-soon/ComingSoon.tsx:9` — `text-gray-600` on the "Not built yet" line. This page IS reachable via `<Route path="*" />` (404 catch-all) so it must adapt. One-line edit: `style={{ color: "var(--ink-muted)" }}`.

`text-gray-600` on `#14130f` is ~2.46:1, below WCAG AA. Same for all the `*-600 / *-700` Tailwind palette values on the dark canvas. The migration is mandatory for accessibility, not just aesthetics.

Full migration sequence + mapping table in [02-execution-plan.md §Shell migration](./02-execution-plan.md).

**StatusBadge — Option A (Tailwind `dark:` variants):**

The generic `StatusBadge` takes `palette: Record<S, string>` (a Tailwind class string). Three feature-level palettes pass these strings:
- `frontend/src/features/targets/StatusBadge.tsx`
- `frontend/src/features/stubs/StatusBadge.tsx`
- `frontend/src/features/scan-runs/StatusBadge.tsx`

Each entry like `"bg-green-100 text-green-800"` gets a `dark:bg-green-900 dark:text-green-100` companion. Tailwind's `darkMode: 'class'` config switches on `<html class="dark">`; the bridge maps the resolved theme to that class.

Existing tests use `expect(el.className).toContain("bg-green-100")` semantics (substring containment). The added `dark:bg-green-900` token in the raw class string does NOT defeat `toContain` — `"bg-green-100"` is still a substring. Tests would only break if they used `className.match(/^bg-/)` or `className.split(" ").filter(c => /^bg-/.test(c)).length` (class-count or anchor-regex). **Pre-implementation check:** grep the 3 feature StatusBadge.test.tsx + StubsList.test.tsx + TargetsList.test.tsx for `^bg-` / `match(/bg/` / `length === N` patterns; record the audit in the spec-review report. If any match, update those assertions mechanically (still asserting both light and new dark companion). Otherwise no test edits.

**No behavioral tests rewritten. Tailwind config gets `darkMode: 'class'`.**

(Option B — semantic-key refactor — was considered. It changes the `StatusBadge` prop shape and breaks ~18 existing test cases across 5 files. Rejected for this slice; tracked as a future cleanup.)

## Token override block (final shape)

`global.css` additions only (other files unchanged for tokens):

```css
/* System pref — applies when no manual override is set */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --surface-canvas: #14130f;
    --surface-raised: #1a1815;
    --surface-sunken: #0f0e0b;
    --ink-strong:  #f0ede4; --ink-default: #d6d3c8;
    --ink-muted:   #9a948a; --ink-soft:    #6b665d;
    --ink-inverse: #14130f;
    --rule-hair:   #2a2823; --rule-soft:   #3a3833; --rule-strong: #4a4842;
    --accent:      #f59e0b; --accent-soft: #4a3a1a;
    --accent-ink:  #fbbf24; --accent-ring: rgba(245, 158, 11, 0.28);
    --accent-wash: rgba(245, 158, 11, 0.08);  /* bumped 4->8% for visibility on dark */
    --ok:   #4ade80; --ok-soft:   #1a3a26; --ok-ink:   #86efac;
    --warn: #fbbf24; --warn-soft: #3a2e15; --warn-ink: #fde68a;
    --err:  #f87171; --err-soft:  #3a1a1a; --err-ink:  #fca5a5;
    --info: #93bbfc; --info-soft: #1a2a4a; --info-ink: #bfdbfe;
    --ok-ring:       rgba(74, 222, 128, 0.28);
    --err-ring:      rgba(248, 113, 113, 0.28);
    --err-ring-soft: rgba(248, 113, 113, 0.18);
    color-scheme: dark;  /* native form controls + scrollbars adopt dark UA chrome */
  }
}

/* Manual override — duplicate the @media token list verbatim here.
   Placed AFTER @media so source order wins on equal-specificity ties. */
:root[data-theme="dark"] {
  /* same tokens as the @media block above */
}
```

**Decision:** duplicate the token list in the `[data-theme="dark"]` block rather than share via CSS `@layer` or selector grouping. Reason: avoids cascade-order surprises against the existing `:root` light-mode block and keeps both paths trivially greppable. During implementation, copy the token list once and compare the two dark blocks before review so they cannot drift.

## Out of scope

- Theme-aware images / logos (no image assets).
- Print stylesheet.
- High-contrast a11y mode (separate token layer; defer).
- Theme transition animation (jarring without; revisit).
- Persisting `"system"` in storage. System mode is represented by removing the `theme` key.

## Tracked follow-ups (not blockers)

- **StatusBadge semantic-key refactor (Option B).** Removes the `dark:` class duplication in feature palettes. Touches ~18 tests; ship as a stand-alone refactor commit after this slice lands.
- **Visual snapshot tests.** Would catch contrast regressions across themes. Not in current test stack (vitest + RTL only); add Playwright + percy/chromatic later.
- **High-contrast mode.** WCAG AAA-grade ramp via a second `[data-theme="dark-hc"]` block.

## Definition of done

- [ ] Implement in the order in [02-execution-plan.md](./02-execution-plan.md).
- [ ] `global.css` dark-token blocks landed; both `@media :root:not([data-theme="light"])` and `:root[data-theme="dark"]` paths active.
- [ ] No-FOUC inline script in `index.html` `<head>` updates both `data-theme` and `.dark` before React.
- [ ] `frontend/src/app/theme.ts` follows the API and edge-case handling in [01-theme-bridge.md](./01-theme-bridge.md).
- [ ] `<ThemeToggle>` consumes the theme store via `useSyncExternalStore`.
- [ ] Topbar 3-state toggle button (`data-testid="theme-toggle"`) cycles light -> dark -> system.
- [ ] Settings page §System status shows `Theme: {current} (resolved: {resolved})`.
- [ ] `tailwind.config.ts` `darkMode: 'class'`; the 3 feature StatusBadge palettes have `dark:` companions on every entry.
- [ ] Tests cover theme storage, invalid values, localStorage errors, missing/stubbed `matchMedia`, system-theme changes, cross-tab storage changes, toggle cycle, Settings row, and StatusBadge dark companions.
- [ ] **Contrast check (operator):** open `/projects`, `/targets`, `/scan-runs`, `/findings`, `/evidence`, `/settings`, AND an unmatched route like `/not-found-check` (exercises the catch-all ComingSoon page) in Chromium with DevTools' "Emulate CSS prefers-color-scheme: dark" + DevTools' Contrast Ratio picker on each status badge / callout / accent underline. Record pass per page in the spec-review report. **WCAG AA thresholds: >=4.5:1 for text, >=3:1 for non-text/UI components.**
- [ ] 497/497 existing vitest passing. **+ new tests:** `theme.test.ts` for the bridge functions and `ThemeToggle.test.tsx` for the 3-state cycle.
- [ ] Spec-review report at `docs/superpowers/spec-reviews/2026-05-20-dark-mode.md` links back to this plan and records test commands plus manual contrast evidence.

## Estimated size

- **Touch points (~30 files):** `frontend/src/styles/global.css`, `frontend/index.html`, `frontend/src/main.tsx` (import-time `applyTheme()` call), new `frontend/src/app/theme.ts` + `theme.test.ts`, new `frontend/src/components/ThemeToggle/ThemeToggle.tsx` + `.module.css` + `.test.tsx`, `frontend/src/app/Layout.tsx` + `Layout.module.css`, `frontend/src/features/settings/Settings.tsx`, the 5 `*FiltersBar.tsx` files, `frontend/src/features/projects/ProjectPickerField.tsx`, `frontend/src/features/scan-runs/CreateScanRun.tsx`, `frontend/src/features/scan-runs/EventsPanelHeader.tsx` + new sibling `EventsPanelHeader.module.css` (step 4f), `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.tsx` + new sibling `ScanRunLiveEventsPanel.module.css` (step 4g — or extend the existing module if present), `frontend/src/features/scan-runs/LifecycleActions.tsx` + new sibling `LifecycleActions.module.css` (step 4h), `frontend/src/features/stubs/StubDetail.tsx`, `frontend/src/features/coming-soon/ComingSoon.tsx`, `frontend/tailwind.config.ts`, and the 3 feature StatusBadge palettes (`frontend/src/features/{targets,stubs,scan-runs}/StatusBadge.tsx`).
- **LOC delta:** ~350 add, no removals.
- Single PR, no backend coordination.
