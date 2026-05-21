---
slice: 03
title: Collapsible sidebar state
depends_on: [02]
---

# Slice 03 — collapsible sidebar

Add a toggle that collapses the sidebar to icon-only width. The collapse state is persistent, cross-tab-synchronised, and accessible.

## Why slice 03 depends on slice 02

The icon-only mode is only useful once icons exist. Slice 02 ships icons; slice 03 ships the affordance to hide labels. Inverting the order would mean shipping a collapsed sidebar that's a blank column.

## Storage contract

Same shape as `frontend/src/app/theme.ts` (in-memory shadow + try/catch + listeners Set + cross-tab `storage` event). The storage listener is registered **once at module load**, not per-subscriber — subscribers only join/leave the `listeners` Set. Both `setCollapsed` and the storage handler early-return when the new value equals the current one, so toggle spam and unrelated tabs don't trigger renders.

```ts
// frontend/src/app/sidebar.ts
const KEY = "em.sidebar.collapsed";
type Collapsed = "true" | "false";

const listeners = new Set<() => void>();
let _mem: Collapsed = readOnce();

function readOnce(): Collapsed {
  try {
    if (typeof window === "undefined") return "false";
    const v = window.localStorage.getItem(KEY);
    return v === "true" ? "true" : "false";
  } catch { return "false"; }
}

function emit() { listeners.forEach((cb) => cb()); }

if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key !== KEY) return;
    const next: Collapsed = e.newValue === "true" ? "true" : "false";
    if (next === _mem) return;
    _mem = next;
    emit();
  });
}

export function isCollapsed(): boolean { return _mem === "true"; }

export function setCollapsed(next: boolean): void {
  const v: Collapsed = next ? "true" : "false";
  if (v === _mem) return;
  _mem = v;
  try { window.localStorage.setItem(KEY, v); } catch {}
  emit();
}

export function subscribeSidebar(cb: () => void): () => void {
  listeners.add(cb);
  return () => { listeners.delete(cb); };
}

export function getSnapshot(): string { return _mem; }
```

- The in-memory `_mem` shadow makes the store survive localStorage-blocked browsers (Safari private mode, embedded webviews).
- `useSyncExternalStore` requires a string snapshot — boolean conversion happens at the React boundary (`snap === "true"`), so the string-typed `Collapsed` is locked in by the API and not a refactor target.
- The `typeof window` guards keep module import safe in non-browser test and SSR-like contexts. Tests that need to verify `readOnce` must use `vi.resetModules()` after mocking storage so module state is rebuilt from the desired setup.
- A generic `createPersistedStringStore(key, allowedValues)` was considered: `theme.ts` and `sidebar.ts` share the same skeleton. Rejected for now (YAGNI with N=2; `theme.ts` carries `matchMedia` + DOM side-effects + tri-state that don't generalise). If a third consumer ships, extract then.

## Toggle component

`frontend/src/components/SidebarToggle/SidebarToggle.tsx` — same pattern as `ThemeToggle`:

```tsx
import { useSyncExternalStore } from "react";
import { ChevronsLeft, ChevronsRight } from "lucide-react";
import { isCollapsed, setCollapsed, subscribeSidebar, getSnapshot } from "../../app/sidebar";
import styles from "./SidebarToggle.module.css";

export function SidebarToggle() {
  const snap = useSyncExternalStore(subscribeSidebar, getSnapshot, () => "false");
  const collapsed = snap === "true";
  return (
    <button
      type="button"
      className={styles.button}
      data-testid="sidebar-toggle"
      data-collapsed={String(collapsed)}
      aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      aria-expanded={!collapsed}
      aria-controls="primary-navigation"
      onClick={() => setCollapsed(!isCollapsed())}
    >
      {collapsed ? (
        <ChevronsRight size={16} aria-hidden focusable="false" />
      ) : (
        <ChevronsLeft size={16} aria-hidden focusable="false" />
      )}
    </button>
  );
}
```

`aria-expanded` is the correct ARIA hook for a disclosure widget that controls an adjacent region (the nav list).

### Styling

`SidebarToggle.module.css` mirrors the existing `frontend/src/components/ThemeToggle/ThemeToggle.module.css` (icon-square button at 1.875rem, `--rule-soft` border, identical `:hover` / `:active` / `:focus-visible` cascade). If a third icon-square button ships later, extract a shared `IconButton` primitive then — not now (YAGNI with N=2).

## Layout wiring

`Layout.tsx`:

```tsx
const snap = useSyncExternalStore(subscribeSidebar, getSnapshot, () => "false");
const collapsed = snap === "true";
return (
  <div className={styles.shell} data-collapsed={String(collapsed)}>
    <aside className={styles.sidebar}>
      <div className={styles.sidebarHeader}>
        {!collapsed && <div className={styles.brand}>Cookbook scanner</div>}
        <SidebarToggle />
      </div>
      <nav id="primary-navigation" aria-label="Primary">
        <ul className={styles.navList}>
          {navItems.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={styles.navLink}
                data-testid={item.testid}
                aria-label={collapsed ? item.label : undefined}
                title={collapsed ? item.label : undefined}
              >
                {/* same icon + label as slice 02 */}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
    {/* … main … */}
  </div>
);
```

The `title={collapsed ? item.label : undefined}` gives a native tooltip only when the label is hidden — no custom popover, no JS, no a11y regression.

The `aria-label` is collapsed-only. In expanded mode the visible text remains the accessible name, which preserves the existing `getByRole("link", { name: "Stubs" })` style queries. In collapsed mode the label span stays in the DOM but is visually hidden by CSS, so `aria-label` supplies the stable name.

## CSS — collapsed variant

`Layout.module.css`:

```css
.sidebarHeader { @apply flex items-center justify-between px-3 pb-3; }
.brand { @apply truncate text-sm font-semibold; color: var(--ink-strong); }
.shell[data-collapsed="true"] { grid-template-columns: var(--sidebar-w-collapsed) 1fr; }
.shell[data-collapsed="true"] .sidebarHeader { justify-content: center; padding-inline: 0; }
.shell[data-collapsed="true"] .label { display: none; }
.shell[data-collapsed="true"] .navLink { justify-content: center; padding-inline: 0; }
.shell { transition: grid-template-columns var(--dur-base) var(--ease-out); }

@media (prefers-reduced-motion: reduce) {
  .shell { transition: none; }
}
```

CSS `grid-template-columns` transitions are supported on all evergreen browsers; if the user opts out via reduced-motion, the change snaps.

## Tests

The full slice-03 test matrix lives in [03-collapsible-state-tests.md](03-collapsible-state-tests.md) to keep this implementation slice under the 200-line plan-file cap.

## File-cap discipline

`sidebar.ts` ≈ 50 lines, `SidebarToggle.tsx` ≈ 25 lines, both tests ≈ 80–100 lines each. None hit the 200-line cap. If `Layout.tsx` exceeds 200 after wiring (currently ~45), extract `<SidebarHeader>` and `<NavList>` rather than compressing — per `feedback_split_dont_compress`.

## Failure modes

- **Forgetting `aria-expanded`.** Without it, screen readers don't announce the state change. Lock it down with the test in step 2.
- **Losing accessible names in collapsed mode.** `display: none` removes the text from the accessibility tree. The collapsed-only `aria-label` is required and should be asserted in `Layout.test.tsx`.
- **`title` showing on expanded labels.** Native browsers double up — `title` + visible label both shown as tooltip. The conditional `title={collapsed ? label : undefined}` prevents this.
- **Importing the store outside a browser.** Module-level `window.addEventListener` must stay guarded. This prevents SSR-like test imports from crashing before React can use the fallback snapshot.
- **Race with theme toggle.** Both stores subscribe to the same `storage` event. They filter by `e.key` and don't interfere; the test in step 4 includes an "unrelated key" case that asserts no spurious re-render of the sidebar store.
