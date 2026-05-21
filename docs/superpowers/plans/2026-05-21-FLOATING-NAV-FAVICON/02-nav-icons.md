---
slice: 02
title: Nav icons
depends_on: []
---

# Slice 02 — nav icons

Add a small icon next to each NavLink label. Pure code-and-data change — no design tokens, no localStorage, no layout shift.

## Dependency

```
<repo-package-manager> add lucide-react@^0.460.0
```

- MIT, zero runtime deps, tree-shakeable per-icon.
- Tree-shaking relies on `lucide-react`'s `sideEffects: false` flag (verified in its `package.json`). Use **named imports from `"lucide-react"`** only — do NOT use `import * as Icons` or per-icon deep paths like `lucide-react/dist/esm/icons/*`; both defeat tree-shaking. Worth a line in the slice commit message so reviewers catch a regression.
- Each imported icon is a React component returning an `<svg>` with `stroke="currentColor"` and `fill="none"`. The icon inherits `color` from the surrounding NavLink, so dark mode "just works" — the colour token already drives ink.
- Expected bundle delta is small when tree-shaking works, but do not treat a per-icon byte estimate as contractual. The implementation agent should inspect the built chunk or dependency analyser output if the bundle size check regresses.

## Icon assignments

```ts
import {
  FolderKanban, Crosshair, ListChecks, Activity,
  AlertCircle, FileSearch, Settings as SettingsIcon,
} from "lucide-react";

const ICONS = {
  projects: FolderKanban,
  targets: Crosshair,
  stubs: ListChecks,
  scanRuns: Activity,
  findings: AlertCircle,
  evidence: FileSearch,
  settings: SettingsIcon,
} as const;
```

Rationale per icon:

| Route | Icon | Why |
|-------|------|-----|
| Projects | FolderKanban | A project groups scopes — folder/board metaphor reads as "container". |
| Targets | Crosshair | Operator language; the recon term is "target". |
| Stubs | ListChecks | Cookbook of checks. Matches existing "stubs list" semantics. |
| Scan Runs | Activity | Time-series of execution. Pairs with the live-events panel. |
| Findings | AlertCircle | Surfaced issues. Avoid `Bug` — too narrow. |
| Evidence | FileSearch | Evidence is a stored artifact with a query/preview affordance. |
| Settings | Settings | The obvious cog. |

## `nav.ts` shape change

```ts
import type { LucideIcon } from "lucide-react";
import { /* … */ } from "lucide-react";
import { ROUTES } from "./routes";

export type NavItem = {
  label: string;
  to: string;
  icon: LucideIcon;
  testid: string;
};

export const navItems: NavItem[] = [
  { label: "Projects",  to: ROUTES.projects,  icon: FolderKanban,  testid: "nav-projects" },
  { label: "Targets",   to: ROUTES.targets,   icon: Crosshair,     testid: "nav-targets" },
  { label: "Stubs",     to: ROUTES.stubs,     icon: ListChecks,    testid: "nav-stubs" },
  { label: "Scan Runs", to: ROUTES.scanRuns,  icon: Activity,      testid: "nav-scan-runs" },
  { label: "Findings",  to: ROUTES.findings,  icon: AlertCircle,   testid: "nav-findings" },
  { label: "Evidence",  to: ROUTES.evidence,  icon: FileSearch,    testid: "nav-evidence" },
  { label: "Settings",  to: ROUTES.settings,  icon: SettingsIcon,  testid: "nav-settings" },
];
```

Adding `testid` is opportunistic — it makes the collapse slice (03) easier to test without depending on label text that may be hidden.

## `Layout.tsx` render change

```tsx
<NavLink to={item.to} className={styles.navLink} data-testid={item.testid}>
  {({ isActive }) => (
    <>
      <item.icon className={styles.icon} size={16} strokeWidth={1.75} aria-hidden focusable="false" />
      <span className={styles.label} data-active={isActive ? "true" : "false"}>
        {item.label}
      </span>
    </>
  )}
</NavLink>
```

The icon is `aria-hidden` because the visible label is the accessible name. When the sidebar is collapsed (slice 03), the icon becomes the sole visible affordance; slice 03 adds `aria-label` for the accessible name and `title` for the native hover tooltip.

## CSS additions

`Layout.module.css`:

```css
.navLink { @apply flex items-center gap-2 px-4 py-2 text-sm; color: var(--ink-default); }
.icon   { @apply shrink-0; }
.label  { @apply truncate; }
```

`gap-2` (8px) is tight enough that 16px icons don't crowd labels.

## Tests

`Layout.test.tsx`:

- Each NavLink renders an `<svg>` (queried via `container.querySelectorAll("nav svg")` → length 7).
- Each NavLink retains its accessible name (label text). Existing tests that query by name (`getByRole("link", { name: "Stubs" })`) must keep passing.
- `data-testid` selectors resolve for all seven routes.

No icon-by-icon assertion — that couples the test to the icon library's component name. Asserting "an svg is present per link" is enough behavioural coverage.

## Failure modes

- **`size` prop drift.** If `lucide-react` changes the prop name in a future major, fail at build time (TypeScript). Use the repo's existing dependency policy for the semver range, and rely on the lockfile for the exact installed version; upgrade deliberately.
- **Bundle bloat from accidental `import * as Icons from "lucide-react"`.** Lint guard: don't do star-imports. Mention in the slice commit message so reviewers catch it.

## Independence

Slice 02 does not depend on slice 01. It does depend on the existing `nav.ts` location. If slice 01 ships first, the icon flex layout drops cleanly into the floating card — `gap-2` works in both card-floating and flush variants.
