# Execution Plan

This file fixes the implementation order, verification matrix, rollback path, and hidden dependencies for [00-overview.md](./00-overview.md).

## Step order

1. **Add dark tokens in `global.css`.**
   - Add the `@media (prefers-color-scheme: dark)` block first.
   - Add the duplicate `:root[data-theme="dark"]` block immediately after it.
   - Confirm both dark token lists are identical before moving on.

2. **Enable Tailwind dark variants.**
   - Set `darkMode: 'class'` in `frontend/tailwind.config.ts`.
   - Add `dark:` companions to every entry in the 3 feature-level StatusBadge palettes.
   - Keep existing light classes in each palette string.

3. **Add the theme bridge.**
   - Add the `index.html` inline script from [01-theme-bridge.md](./01-theme-bridge.md).
   - Add `frontend/src/app/theme.ts` with the storage, DOM sync, and subscription contract.
   - Make sure both the inline script and `applyTheme()` update `data-theme` and `.dark`.
   - **Edit `frontend/src/main.tsx`:** add a top-level `import { applyTheme } from "./app/theme"; applyTheme();` BEFORE `ReactDOM.createRoot(...).render(...)`. This reconciles any storage change that happened between the inline script and React boot (e.g. user clicked the toggle in another tab during the load).

4. **Hardcoded-Tailwind migration (14 files).** Order doesn't matter — all are independent file edits. The full list + mapping rationale is in [00-overview.md §Components that need attention](./00-overview.md). Execution sub-steps:

   - 4a. `frontend/src/app/Layout.module.css`: replace each Tailwind `@apply bg-gray-* / text-gray-* / border-gray-* / bg-white` with `var(--surface-*)` / `var(--ink-*)` / `var(--rule-*)` tokens. Map: `bg-gray-50` → `var(--surface-sunken)`, `border-gray-200` → `var(--rule-hair)`, `text-gray-700` → `var(--ink-default)`, `bg-white` → `var(--surface-raised)`, `text-gray-900` → `var(--ink-strong)`, `hover:bg-gray-100` → CSS hover rule using `var(--surface-sunken)`.
   - 4b. `frontend/src/features/settings/Settings.tsx`: replace `className="text-gray-500"` / `text-green-700` / `text-red-700` / `text-amber-700` with token-driven `style={{ color: "var(--…)" }}` mapping ok/warn/err/muted to `--ok` / `--warn` / `--err` / `--ink-muted`.
   - 4c. 5 FiltersBars (`features/{targets,scan-runs,findings,evidence,stubs}/*FiltersBar.tsx`): replace **every** `<span className="text-gray-600">` (some files have 2 — `EvidenceFiltersBar.tsx` at lines 44 + 75) with `style={{ color: "var(--ink-muted)" }}`. Audit each file end-to-end before moving on.
   - 4d. `frontend/src/features/projects/ProjectPickerField.tsx:42`: `border border-gray-300` on `<select>` → `border: '1px solid var(--rule-soft)'` via style or a small CSS module.
   - 4e. `frontend/src/features/scan-runs/CreateScanRun.tsx`: line 150 `border-gray-300` on `<select>` → `var(--rule-soft)`; lines 170, 195 `text-gray-600` → `var(--ink-muted)`.
   - 4f. `frontend/src/features/scan-runs/EventsPanelHeader.tsx` (lines 4-9): STATUS_CLASS map. Create a sibling `EventsPanelHeader.module.css` with status-tinted backgrounds via tokens (`.connected { background: var(--ok-soft); color: var(--ok-ink); }` etc.); replace the Tailwind class-string map with `data-status={status}` + module selectors. Mirrors the StatusBadge polish pattern.
   - 4g. `frontend/src/features/scan-runs/ScanRunLiveEventsPanel.tsx` (lines 22-25): LEVEL_CLASS map. Same approach as 4f — sibling `.module.css` with `[data-level="debug"] { color: var(--ink-muted); background: var(--surface-sunken); }`, `[data-level="info"]` → info tokens, `warning` → warn, `error` → err.
   - 4h. `frontend/src/features/scan-runs/LifecycleActions.tsx:14`: `bg-gray-200 hover:bg-gray-300` on `<button>` → use `var(--surface-sunken)` + CSS hover with `var(--surface-canvas)` via a small `.module.css`.
   - 4i. `frontend/src/features/stubs/StubDetail.tsx:28`: `<pre>` styling `bg-gray-50 border-gray-200` → `background: var(--surface-sunken); border: 1px solid var(--rule-hair);`.
   - 4j. `frontend/src/features/coming-soon/ComingSoon.tsx:9`: `<p className="text-gray-600">` → `style={{ color: "var(--ink-muted)" }}`. One-line edit.

   After all 14, re-run the same audit command as in [00-overview.md §Components](./00-overview.md): `rg -n '(text|bg|border)-(gray|blue|green|amber|red|yellow|orange)-|bg-white|border-white' frontend/src/ --type-add 'web:*.{tsx,ts,css}' -tweb -g '!*.test.*' -g '!*StatusBadge*'` should return **zero results**. The `-g '!*.test.*' -g '!*StatusBadge*'` flags exclude test files (which still assert legacy class names until step 6 rewrites them) and StatusBadge files (which use the Tailwind-`dark:` companion approach in step 2, not the token migration).

5. **Add UI integration.**
   - Add `<ThemeToggle>` with a 3-state cycle and `data-testid="theme-toggle"`.
   - Mount it in the topbar next to `<ConnectionPill>`.
   - Add the Settings §System status Theme row.

6. **Add tests + update existing class-string assertions.**
   - Add focused tests for `theme.ts`, `ThemeToggle`, Settings row, and StatusBadge dark companions.
   - Add a Layout token-reference test (static-file grep — see the §Layout shell test entry in the Test matrix below). JSDOM cannot resolve CSS custom properties; resolved-colour verification lives in Step 7 (manual contrast check).
   - **Update existing tests broken by step 4f/4g** (the EventsPanelHeader + ScanRunLiveEventsPanel migrations replace Tailwind class strings with `data-status` / `data-level` attribute selectors). Known affected: `ScanRunLiveEventsPanel.rows.test.tsx:104` (assertions via `toContain(expectedClass)` where `expectedClass` is bound from a `cases` array on lines 90-95 holding literal strings like `"text-blue-600 bg-blue-100"`). Replace those assertions with `data-level={level}` attribute checks against the `<tr>` or wrapper.
   - To catch any others before declaring step 4 done, run **all three** of these greps and update every hit:
     - `rg -n 'toMatch\(/(bg|text)-(blue|green|amber|red|gray)' frontend/src --type-add 'web:*.{tsx,ts}' -tweb` — direct regex assertions.
     - `rg -n 'toContain\(.*(bg|text)-(blue|green|amber|red|gray)' frontend/src --type-add 'web:*.{tsx,ts}' -tweb` — `toContain(string literal)` assertions.
     - `rg -n '"(bg|text)-(blue|green|amber|red|gray)-' frontend/src -g '*.test.*'` — literal Tailwind class strings anywhere in test files (catches `cases`/data-table patterns where the assertion uses a bound variable).
   - The third grep is the broadest and is the one that actually surfaces `ScanRunLiveEventsPanel.rows.test.tsx`; treat its output as the authoritative list.
   - Run the existing vitest command and keep the test count at or above 497 (a small number of tests may grow assertions; none should disappear).

7. **Do manual contrast verification.**
   - Check `/projects`, `/targets`, `/scan-runs`, `/findings`, `/evidence`, `/settings`, AND one unmatched route (e.g. `/not-found-check`) so the catch-all `<ComingSoon name="Not found" />` page is exercised — that's now in the migration scope (item 14).
   - For each route, check **at minimum**: 1 StatusBadge per variant present on the page (ok/warn/err/info/muted), 1 Callout variant per variant present (info/warning/error), the PageHeader title + amber underline accent, the EmptyState diagonal stripe (where reachable), and 1 Table row hover.
   - Record each check in a table in `docs/superpowers/spec-reviews/2026-05-20-dark-mode.md`, using **exactly this row schema**:

   | Route | Control | Selector | Foreground | Background | Ratio | Threshold | Pass |
   | --- | --- | --- | --- | --- | --- | --- | --- |
   | `/scan-runs` | StatusBadge "running" | `[data-testid="status-running"]` | `#fbbf24` | `#1a1815` | 9.34:1 | 4.5:1 | ✓ |

   Threshold column uses `4.5:1` for text inside the control, `3:1` for non-text/UI (border, dot, accent underline). Pass = ✓ / ✗. Use Chrome DevTools' Contrast Ratio picker (Inspect → Styles panel → click the color swatch). The spec-review report must contain a complete table for both Forced-Dark and System-Dark resolutions.

## Test matrix

`theme.test.ts`:
- `getTheme()` returns `system` for missing, invalid, and storage-error cases.
- `setTheme("light")` writes `"light"`, sets `data-theme="light"`, and removes `.dark`.
- `setTheme("dark")` writes `"dark"`, sets `data-theme="dark"`, and adds `.dark`.
- `setTheme("system")` removes the key, removes `data-theme`, and reflects `matchMedia`.
- `setTheme("dark")` with `localStorage.setItem` mocked to throw → `getTheme()` still returns `"dark"` (in-memory shadow), `data-theme="dark"` set, `.dark` added, `themechange` event fires. Cross-tab `storage` listener won't see it; that's expected degradation.
- `setTheme(<garbage>)` (cast to bypass TS) → falls back to `"system"`.
- `resolvedTheme()` follows `matchMedia` only in system mode.
- `subscribeTheme()` notifies on `themechange`, relevant `storage` events, and system changes only while current theme is system.
- A cross-tab `storage` event with `key === "theme"` re-syncs the in-memory shadow from storage before calling `applyTheme`.
- JSDOM `matchMedia` stubs are installed and cleaned up per test.

`ThemeToggle.test.tsx`:
- Renders current state with a sun/moon/monitor glyph.
- Accessible name includes current and next state.
- Click order is light -> dark -> system -> light.
- System mode removes the storage key instead of storing `"system"`.
- A mocked system-theme change updates the resolved label without remounting.

Settings test:
- §System status includes `Theme: {current} (resolved: {resolved})`.
- The row updates after toggling the topbar control.
- Status colour spans (db/redis/worker `up`/`down`, backend `ok`/`degraded`) compute against `var(--ok)` / `var(--err)` / `var(--warn)` — not the prior `text-green-700` / `text-red-700` / `text-amber-700` literals.

Layout shell test:
- **JSDOM caveat:** the repo's `jsdom@25` does NOT resolve CSS custom properties — `getComputedStyle(el).backgroundColor` returns the literal `var(--surface-sunken)` string (or empty), not the resolved RGB. So the test cannot assert resolved colours.
- Instead: assert that `Layout.module.css` references the right tokens via static-file grep in a vitest (e.g. `expect(layoutCss).toContain("var(--surface-sunken)")` after `fs.readFileSync`). This catches accidental token regressions without depending on JSDOM resolution.
- Resolved-colour verification belongs in the manual-contrast step (real Chromium, DevTools' contrast picker — see Step 7).

StatusBadge tests:
- Every palette entry keeps its light `bg-* text-*` classes.
- Every palette entry includes a matching `dark:bg-* dark:text-*` companion.
- If an existing exact class-string assertion fails, update that assertion only to include the new dark classes.

## Edge cases

- `localStorage` can throw in restricted browser modes; all reads/writes must be wrapped.
- `matchMedia` can be missing in JSDOM and older browser contexts; tests must stub it or code must guard it.
- Older media-query list APIs may expose `addListener/removeListener` instead of `addEventListener/removeEventListener`.
- Invalid stored theme values must behave exactly like system mode.
- Cross-tab theme changes should update the DOM through the `storage` event.
- A system-dark user in system mode must get `.dark` before React mounts, not only after the first React render.
- Light mode must not change any existing `:root` token values.

## Hidden dependencies

- Tailwind `dark:` variants do nothing until `darkMode: 'class'` is enabled and `<html class="dark">` is present.
- CSS token dark mode and Tailwind dark variants are separate systems; both must be synchronized.
- Duplicated dark token blocks can drift. Treat a mismatch between `@media` and `[data-theme="dark"]` as a blocker.
- Existing StatusBadge tests may assert exact class strings. Those are brittle but not behavioral; keep changes mechanical if they fail.
- The spec-review report path is outside this plan tree. This plan may link to it, but implementation should create it only during the dark-mode feature work.
- **Native form-control chrome (selects, scrollbars, focus rings) follows the `color-scheme` CSS property** — not the token colour values. Both dark token blocks (the `@media` block and the `[data-theme="dark"]` block) must include `color-scheme: dark;` so unstyled `<select>` controls in the 5 FiltersBars render with dark UA chrome instead of light.
- **JSDOM does not resolve CSS custom properties.** Vitest tests cannot assert `getComputedStyle(el).backgroundColor` against a token; resolved-colour verification must use real Chromium (manual contrast step).

## Rollback

Immediate operator mitigation:
- Toggle back to light, which writes `localStorage.theme = "light"` and forces light tokens even on an OS-dark machine.
- If the toggle itself is broken but DevTools access is available, run `localStorage.setItem("theme", "light"); location.reload();`.

Code rollback path:
- Remove `<ThemeToggle>` from the topbar and remove the Settings row.
- Remove the `index.html` inline script and `frontend/src/app/theme.ts`.
- Remove `darkMode: 'class'` only if no other app code uses Tailwind `dark:` variants.
- Remove `dark:` companions from the 3 StatusBadge palettes.
- Remove both dark token blocks from `global.css`.

Rollback must leave all original light-mode token values and StatusBadge light classes untouched.

## Acceptance evidence

The spec-review report should record:
- The exact test command used and pass count.
- The routes and controls checked for contrast.
- Any exact-class test assertions updated because of `dark:` companion classes.
- Confirmation that `localStorage` blocked, missing `matchMedia`, invalid storage value, and system-theme-change cases were tested.
