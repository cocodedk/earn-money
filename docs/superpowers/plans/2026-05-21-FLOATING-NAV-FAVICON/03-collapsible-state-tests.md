---
slice: 03-tests
title: Collapsible sidebar tests
parent: 03-collapsible-state.md
---

# Slice 03 — tests

These tests belong to [03-collapsible-state.md](03-collapsible-state.md). Keep them with slice 03 even if the implementation commits are split.

## `SidebarToggle.test.tsx`

Five assertions:

1. Initial render: button is present, `aria-expanded="true"`, glyph is `ChevronsLeft`.
2. Click: `setCollapsed` was called with `true`; `aria-expanded` flips to `"false"`.
3. localStorage `em.sidebar.collapsed` reads `"true"` after click.
4. Storage event from another tab (`new StorageEvent("storage", { key: KEY, newValue: "true" })`) updates rendered state.
5. With `localStorage.setItem` patched to throw, click still updates the in-memory shadow and the rendered glyph.

## `sidebar.test.ts`

Direct store tests:

- `readOnce` returns `"false"` on storage failure.
- `setCollapsed(true)` then `setCollapsed(false)` round-trips cleanly.
- `setCollapsed` to the current value does NOT emit (no-op guard).
- `subscribeSidebar` listener fires on `setCollapsed` when the value changes.
- `subscribeSidebar` listener fires on cross-tab `storage` event with the right key, ignores other keys.
- Storage event with `newValue === currentValue` does NOT emit (no-op guard).
- `subscribeSidebar` returned teardown removes the listener from the Set; subsequent `setCollapsed` does not invoke it.
- Import-time storage tests use `vi.resetModules()` after mocking storage so the module-level `_mem` value is rebuilt for each setup.

## `Layout.test.tsx`

Two new cases:

- When `localStorage` has `em.sidebar.collapsed = "true"` at render time, the shell root has `data-collapsed="true"` and every nav link remains findable by accessible name.
- The NavLink has both `aria-label` and `title` equal to the label when collapsed, and neither attribute when expanded.
