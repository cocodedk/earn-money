---
slice: 01
title: Floating sidebar
depends_on: []
---

# Slice 01 — floating sidebar

Turn the flush-against-edge sidebar into a discrete floating card. **CSS only** — no React component changes, no nav data changes. This slice is intentionally tiny so the design move can be reviewed in isolation.

## Current shape

`frontend/src/app/Layout.module.css`:

```css
.shell { @apply h-full grid; grid-template-columns: 240px 1fr; }
.sidebar {
  @apply flex flex-col py-4;
  background: var(--surface-sunken);
  border-right: 1px solid var(--rule-hair);
}
```

The sidebar is the left grid column, touching the viewport edge and the topbar.

## Target shape

The shell becomes a single canvas. The sidebar is a card with padding around it on all four sides, a 1px hairline border, a corner radius, and a soft shadow. The topbar sits to the right of (not above) the sidebar gutter.

```css
.shell {
  @apply h-full grid gap-3 p-3;
  grid-template-columns: var(--sidebar-w, 240px) 1fr;
  background: var(--surface-canvas);
}
.sidebar {
  @apply flex flex-col py-3 rounded-md;
  background: var(--surface-raised);
  border: 1px solid var(--rule-hair);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.main {
  @apply flex flex-col min-w-0 rounded-md overflow-hidden;
  border: 1px solid var(--rule-hair);
  background: var(--surface-raised);
}
.topbar {
  /* unchanged height + flex; keep an internal separator above scrollable content */
  @apply h-14 flex items-center justify-between px-6;
  background: var(--surface-raised);
  border-bottom: 1px solid var(--rule-hair);
}
```

## Token additions

`frontend/src/styles/global.css` `:root`:

```css
--shadow-card: 0 1px 2px rgba(10, 10, 10, 0.04), 0 4px 12px rgba(10, 10, 10, 0.04);
--sidebar-w: 240px;       /* expanded; the collapse slice overrides */
--sidebar-w-collapsed: 56px;
```

Dark override block (both `@media (prefers-color-scheme: dark)` and `[data-theme="dark"]`):

```css
--shadow-card: 0 1px 2px rgba(0, 0, 0, 0.4), 0 4px 12px rgba(0, 0, 0, 0.35);
```

Dark needs a stronger shadow because surfaces sit closer in luminance — the soft light-mode shadow disappears entirely against `--surface-canvas: #14130f`.

## Why surface-raised and not surface-sunken

The card pattern depends on the canvas being **darker** than the card in light mode (`--surface-canvas: #faf9f6` < `--surface-raised: #fff`) and **lighter** than the card in dark mode (`--surface-canvas: #14130f` < `--surface-raised: #1a1815`). Both directions read as "lifted". The current sunken sidebar was inverted for the flush layout; for floating we want raised.

## Test coverage

`Layout.test.tsx` adds two assertions:

- `screen.getByRole("complementary")` (the `<aside>`) has class containing `rounded-md`.
- The shell's computed `display: grid` is preserved.

JSDOM resolves classNames but not CSS custom properties — don't try to assert shadow values. Class presence is enough to detect a regression.

## Failure modes

- **Border + shadow stack too heavy in dark mode.** If the card edge looks like a double rim, drop the dark border to `--rule-soft` and rely on shadow alone.
- **Topbar inside the main card breaks long-content scroll.** The main card uses `overflow-hidden` on the outer and the `content` already does `overflow-auto` — the existing behaviour is preserved; verify on Stubs/Findings (long lists).
- **Sticky positioning.** Nothing in the current layout is `position: sticky` inside the sidebar; the floating change does not introduce one. Future "sticky topbar inside card" work is out of scope.

## Slice boundary

Slice 01 ships in one commit. No icon work, no collapse state, no favicon. The next slice (02) adds icons but does **not** require slice 01 to land first — the slices can be reordered if review needs it.
