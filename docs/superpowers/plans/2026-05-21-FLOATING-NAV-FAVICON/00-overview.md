---
title: Floating nav + favicon
status: draft
owner: agent-em-frontend
date: 2026-05-21
related_specs: []
---

# Floating nav + favicon — overview

Four UI improvements to the operator-console shell. The current sidebar is a flush 240px grid column with text-only links. After this plan it will be a **floating panel** with **icons next to labels** that **collapses to icon-only** with native-tooltip text, and the browser tab will show a real **favicon** instead of the Vite default.

## Goals

1. **Floating sidebar.** Visual panel inside a gutter — rounded card with a soft border + shadow. Reads as a discrete surface, not edge-of-page chrome. Light + dark both look intentional.
2. **Icon per nav item.** A small leading icon for each of the seven routes (Projects, Targets, Stubs, Scan Runs, Findings, Evidence, Settings). Matches the thin-stroke Operator Console aesthetic.
3. **Collapsible sidebar.** A toggle at the top of the sidebar shrinks it to icon-only width. Native `title` attribute provides hover tooltips so the label is still discoverable. State persists across reloads via `localStorage` and syncs across tabs.
4. **Favicon.** A small mark in the brand amber, served as SVG + PNG fallbacks + Apple Touch + ICO. Replaces the Vite default and gives the browser tab an identity.

## Non-goals

- No mobile drawer / off-canvas behaviour. This pass is desktop-first; the existing layout already assumes ≥1024px.
- No icon library swap later. Pick one library now, stick to it.
- No SVG hand-roll for individual nav icons. Use a maintained icon set so additions are trivial.
- No third-party favicon upload service. The mark is small enough to author locally; we don't want our source SVG indexed by a generator site.

## Constraints

- React 18, Vite, TypeScript strict, Tailwind v3 with `darkMode: "class"`, CSS modules + CSS-variable tokens.
- All production code under strict TDD with 100% line + branch coverage (CLAUDE.md rule).
- 200-line file cap on code, tests, HTML, CSS, config (CLAUDE.md rule).
- Existing dark-mode tokens stay untouched. Any new app-UI colour goes through `--*` tokens, never hardcoded hex. Standalone favicon assets may use literal fallback colours because the browser loads them outside the app CSS cascade; those values must be copied from existing token values and documented in [04-favicon.md](04-favicon.md).
- Existing testids and behaviour on already-shipped pages must not regress. The seven NavLink targets and their text labels must remain reachable by the same test queries (label match by accessible name).

## Library choices (decided in this plan, not asked of operator)

- **Icon library:** `lucide-react`. MIT, tree-shakeable, thin-stroke, 1000+ icons, zero runtime, identical SSR/CSR. No competing weights to worry about; use named imports and verify bundle size if the build check regresses.
- **Persistence pattern:** Reuse the `useSyncExternalStore` + localStorage shadow pattern already proven in `frontend/src/app/theme.ts`. Same `_memShadow` fallback for storage-blocked browsers. Same cross-tab `storage`-event sync.
- **Favicon generation:** Hand-authored SVG → rasterised locally. Prefer repo-local generator tooling; if none exists, add a pinned generator dev dependency in the favicon commit and commit the lockfile. Do not assume global binaries or transitive packages are present. No web upload; everything stays in the repo. See [04-favicon.md](04-favicon.md) for the decision record on web-skill alternatives.

## Slices

| File | What it covers |
|------|----------------|
| [01-floating-sidebar.md](01-floating-sidebar.md) | Sidebar becomes a floating card. CSS-only change. |
| [02-nav-icons.md](02-nav-icons.md) | `lucide-react` dependency + icon map + nav.ts shape change. |
| [03-collapsible-state.md](03-collapsible-state.md) | Sidebar-collapsed store, toggle button, collapsed CSS, tooltips. |
| [04-favicon.md](04-favicon.md) | Favicon SVG + PNG/ICO fallbacks + `<link>` tags in `index.html`. |
| [05-execution-plan.md](05-execution-plan.md) | Commit-by-commit order with TDD step pairs and verification gates. |

## Definition of done

- Sidebar renders as a floating card in both themes; topbar and content unaffected.
- Each NavLink renders icon + label; label vanishes in collapsed mode.
- Toggle persists across reloads; survives storage-blocked browsers via in-memory shadow.
- Hovering a collapsed icon shows the route label via native tooltip (no custom popover), and the collapsed link keeps the same accessible name via `aria-label`.
- `prefers-reduced-motion: reduce` disables the collapse transition.
- `/favicon.svg`, `/favicon.ico`, `/favicon-32.png`, `/apple-touch-icon.png` all 200 OK from the dev server.
- All Vitest suites green; coverage stays at 100% on touched files.
- Manual smoke: all seven routes navigable in both states, in both themes.
- `Layout.test.tsx` + new `ThemeToggle`-style tests for sidebar-collapse store assert behaviour, not implementation.
