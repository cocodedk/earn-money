---
slice: 05
title: Execution plan
depends_on: [01, 02, 03, 04]
---

# Slice 05 — execution plan

Commit-by-commit order. Each commit is its own PR-able unit, leaves the tree green, and is independently revertable.

## Branch + stack convention

Per `project_stacked_branch_convention` memory, each new branch stacks on the previous tip — not on main. The merge-tip squash-collapses the stack.

```
main
 └── feat/em-frontend-floating-shell        ← slice 01 commits
      └── feat/em-frontend-nav-icons        ← slice 02 commits
           └── feat/em-frontend-sidebar-collapse  ← slice 03 commits
                └── feat/em-frontend-favicon       ← slice 04 commits
```

Squash-merge the tip; the stack folds into one main commit.

## Preflight

- Confirm the frontend package manager from the existing lockfile, then use that same manager for `lucide-react` and any favicon generator dependency.
- Check touched file line counts before each commit. If any source, test, CSS, HTML, or config file would exceed 200 lines, extract a small component/helper/test file instead of compressing content.
- Before slice 04, check whether favicon generator tooling is already repo-local. If it is not, follow the fallback in [04-favicon.md](04-favicon.md) instead of assuming a global binary.
- Confirm the current paths still match this plan (`frontend/src/app/Layout.tsx`, `Layout.module.css`, `nav.ts`, `theme.ts`, `frontend/public/`, `frontend/index.html`). If a path has moved, update the affected slice doc first so cross-references stay truthful.

## Commit sequence

### Slice 01 — floating shell

1. **chore(frontend): add --shadow-card token (light + dark).**
   - `global.css` only. No visual change yet (no consumer).
   - Test: none needed (token addition is data).
2. **feat(frontend): floating sidebar + content cards.**
   - Edit `Layout.module.css` per slice 01.
   - Update `Layout.test.tsx`: assert `aside` has `rounded-md` class, shell grid preserved.
   - Run vitest → green.

### Slice 02 — nav icons

3. **chore(frontend): add lucide-react dependency.**
   - Install `lucide-react@^0.460.0` with the repo's existing package manager — package.json + lock only.
4. **feat(frontend): nav items render leading icons.**
   - Update `nav.ts` shape (add `icon`, `testid`).
   - Update `Layout.tsx` render.
   - Update `Layout.module.css` (`.navLink` becomes flex, `.icon`, `.label`).
   - Update `Layout.test.tsx`: `container.querySelectorAll("nav svg")` length is 7.
   - Run vitest → green; visual smoke in dev server.

### Slice 03 — collapsible sidebar

5. **feat(frontend): sidebar-collapsed store + tests.**
   - New `frontend/src/app/sidebar.ts` (≈50 lines).
   - New `frontend/src/app/sidebar.test.ts` (≈100 lines, mirrors `theme.test.ts`).
   - No render change yet — store is independently testable.
6. **feat(frontend): SidebarToggle component + tests.**
   - New `frontend/src/components/SidebarToggle/SidebarToggle.tsx`.
   - New `SidebarToggle.test.tsx`.
   - Component exported but not yet mounted.
7. **feat(frontend): wire SidebarToggle into Layout + collapsed CSS.**
   - Edit `Layout.tsx`: subscribe via `useSyncExternalStore`, render toggle in sidebar header, set `data-collapsed` on `.shell`.
   - Collapsed links must set both `aria-label={item.label}` and `title={item.label}`; expanded links must rely on visible text and omit both attributes.
   - Edit `Layout.module.css`: `[data-collapsed="true"]` cascade.
   - Edit `Layout.test.tsx`: collapsed-mode assertions per slice 03 spec.
   - Vitest green; visual smoke at 240px and 56px widths.

### Slice 04 — favicon

8. **chore(frontend): add favicon assets + index.html links.**
   - Author `frontend/public/favicon.svg`.
   - Run local rasterise commands (slice 04 spec) → commit the four asset files. If generator dev dependencies are added for reproducibility, include package.json + lockfile in this commit or split them into a preceding `chore(frontend): add favicon generator tooling` commit.
   - Edit `index.html` (four `<link>` tags inserted before the theme script, including the PNG fallback).
   - New `frontend/src/app/document-head.test.tsx` static-grep tests.
   - Vitest green.

## TDD discipline

Each commit follows the **failing test → minimal code → green** loop required by CLAUDE.md. For commits without a new test (commit 1, 3), the prior test suite must remain green and coverage on touched files must remain at 100%.

Order of operations per commit:

1. Write the failing test first.
2. Write the minimal production code.
3. Run the repo-package-manager equivalent of `npm run test --silent` from `frontend/`. Must pass.
4. Run the repo-package-manager equivalent of `npm run typecheck` (or `tsc --noEmit`).
5. Stage **specific files only** (memory rule `feedback_stage_specific_files`).
6. Commit with a Conventional-Commits message + `Co-Authored-By: Claude Opus 4.7`.
7. Run `/simplify` if available. If the command is not available in the agent environment, do a manual simplify pass focused on duplication, line caps, and unnecessary abstraction. Iterate fix → re-run until clean.
8. Move to next commit.

## Verification gates

Before declaring the whole feature done:

- The repo test command reports 0 failures, coverage on `frontend/src/app/*`, `frontend/src/components/SidebarToggle/*` at 100% lines + branches.
- Dev server: open all seven routes in both themes, both collapse states.
- Accessibility smoke: in expanded and collapsed modes, all seven nav links are still findable by role and accessible name.
- Curl checks for all four favicon assets pass.
- Favicon dimensions verify locally: PNG is 32×32, Apple icon is 180×180, ICO contains 16/32/48/64.
- `git log origin/main..HEAD` shows the expected commit shape; no `--no-verify` skipped hooks.
- The PR description for the tip branch summarises the four slices and links this plan.

## Rollback plan

- Revert from the tip of the stack backwards unless deliberately cherry-picking a lower slice; slice 03 depends on slice 02, so reverting icons while leaving collapse creates an icon-only blank column.
- Slice 01 rollback is CSS/token-only. Revert the floating shell commit and remove unused `--shadow-card` only if no later slice consumes it.
- Slice 02 rollback removes the `lucide-react` dependency, `icon` fields, testids added only for collapse, and icon render markup. Keep route labels and link targets unchanged.
- Slice 03 rollback removes `sidebar.ts`, `SidebarToggle`, Layout wiring, and collapsed CSS. The stale `em.sidebar.collapsed` localStorage key is harmless; no migration is needed.
- Slice 04 rollback removes `index.html` favicon links and generated assets. Browser favicon caches may continue showing the reverted mark until cache expiry or hard refresh.

## Out-of-scope follow-ups (capture, don't ship)

- Mobile drawer (`<768px` breakpoint) — separate slice if needed.
- A "system" mode for the sidebar (auto-collapse based on viewport width) — defer.
- Animated icon → state transitions (e.g. spinning Activity icon when a scan is running) — defer; touches per-page state.
- Replacing the SVG mark with a logo authored by a designer — defer; current mark is a placeholder consistent with the operator-console aesthetic.
