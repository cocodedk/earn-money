# 19. Component primitives

Every primitive lives at `src/components/<Name>/` and ships as a folder of paired files:

```
src/components/Button/
  Button.tsx
  Button.module.css
  Button.test.tsx
  index.ts        # re-export
```

Each `.tsx` / `.module.css` / `.test.tsx` stays under the 200-line cap. Tests assert on `data-testid` and ARIA role, never on Tailwind class names.

## Button

Variants: `primary` | `secondary` | `danger`. States: `disabled`, `loading` (spinner replaces label, button stays the same width).

```ts
type ButtonProps = {
  variant?: "primary" | "secondary" | "danger";
  loading?: boolean;
  disabled?: boolean;
  type?: "button" | "submit";
  onClick?: () => void;
  children: ReactNode;
};
```

Test handle: `data-testid="button"` + `data-variant`.

## Table + TableSkeleton

Generic typed table. Header / row / empty / loading slots.

```ts
type TableColumn<T> = {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  width?: string;
};

type TableProps<T> = {
  columns: TableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  isLoading?: boolean;       // → TableSkeleton (5 rows)
  emptyState?: ReactNode;    // → rendered when rows.length === 0
};
```

## StatusBadge / SeverityBadge

Typed enum prop. Colours come from `18-design-tokens.md`. Never accepts arbitrary strings.

```ts
type ScanRunStatus = "queued" | "running" | "paused" | "stopping" | "stopped" | "failed" | "done";
type Severity = "info" | "low" | "medium" | "high" | "critical";
```

## TextInput / Textarea / FormField

`FormField` composes a label, an input (`TextInput` or `Textarea`), and an optional error string. When `error` is set, the input gets a red border and `aria-invalid="true"`; the error text renders below with `aria-describedby` wiring.

```ts
type FormFieldProps = {
  label: string;
  htmlFor: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
};
```

## Callout

Variants: `info` | `warning` | `error`. Used for top-of-page banners, validation banners, and error states inside lists.

```ts
type CalloutProps = {
  variant: "info" | "warning" | "error";
  title?: ReactNode;
  children: ReactNode;
  action?: { label: string; onClick: () => void };
};
```

## EmptyState

Plain, centered text + optional action button. No icon.

```ts
type EmptyStateProps = {
  message: string;
  action?: { label: string; onClick: () => void };
};
```

## ConnectionPill

Top-bar component fed by `useConnectionStatus()`. Green dot + "Connected" / red dot + "Disconnected". Polls `/api/health/` on mount + every 30s.

## PageHeader

Slot composition: title on the left, optional action node on the right.

```ts
type PageHeaderProps = {
  title: string;
  action?: ReactNode;
};
```

## ComingSoon

Placeholder route handler used by slice 1 for nav items not yet built (Targets, Stubs, Scan Runs, Findings, Evidence, Settings). Single-purpose: shows the page name + "Not built yet." string.

## Conventions

- Props typed exhaustively; no `any`, no `unknown` props.
- All interactive elements expose a visible focus ring (`@apply ring-2 ring-blue-500 ring-offset-1`) on `:focus-visible`.
- All components ship with at least one render test asserting the spec's behaviour (e.g. "Button disables on loading", "Callout error renders the action").
