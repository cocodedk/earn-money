# Phase 2 — Component primitives

Six low-level UI components, each in its own folder. Every component ships with at least 2 tests. Style via `@apply` in `.module.css` next to the `.tsx`.

The pattern for every primitive:

```
src/components/<Name>/
  <Name>.tsx
  <Name>.module.css
  <Name>.test.tsx
  index.ts        # `export * from "./<Name>";`
```

`index.ts` is always one line; test handles use `data-testid` so class names can change freely.

---

### Task G: `Button`

**Files:**
- Create: `frontend/src/components/Button/Button.tsx`
- Create: `frontend/src/components/Button/Button.module.css`
- Create: `frontend/src/components/Button/Button.test.tsx`
- Create: `frontend/src/components/Button/index.ts`

- [ ] **Step 1: Write `Button.test.tsx`**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";

describe("Button", () => {
  it("renders children and fires onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("disables and swaps label for spinner when loading", () => {
    render(<Button loading>Save</Button>);
    const button = screen.getByRole("button");
    expect(button).toBeDisabled();
    expect(screen.getByTestId("button-spinner")).toBeInTheDocument();
    expect(screen.queryByText("Save")).not.toBeInTheDocument();
  });

  it("renders the danger variant", () => {
    render(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole("button")).toHaveAttribute("data-variant", "danger");
  });
});
```

- [ ] **Step 2: Run, see fail**

```bash
cd frontend && npm run test -- src/components/Button
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement `Button.tsx`**

```tsx
import { ReactNode } from "react";
import styles from "./Button.module.css";

export type ButtonProps = {
  variant?: "primary" | "secondary" | "danger";
  loading?: boolean;
  disabled?: boolean;
  type?: "button" | "submit";
  onClick?: () => void;
  children: ReactNode;
};

export function Button({
  variant = "primary",
  loading = false,
  disabled = false,
  type = "button",
  onClick,
  children,
}: ButtonProps) {
  const className = `${styles.btn} ${styles[variant]}`;
  return (
    <button
      type={type}
      className={className}
      disabled={disabled || loading}
      onClick={onClick}
      data-testid="button"
      data-variant={variant}
    >
      {loading ? (
        <span className={styles.spinner} data-testid="button-spinner" />
      ) : (
        children
      )}
    </button>
  );
}
```

- [ ] **Step 4: Implement `Button.module.css`**

```css
.btn {
  @apply inline-flex items-center justify-center h-10 px-4 rounded font-medium text-sm;
  @apply disabled:opacity-50 disabled:cursor-not-allowed;
}
.primary {
  @apply bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800;
}
.secondary {
  @apply bg-white text-gray-900 border border-gray-200 hover:bg-gray-50;
}
.danger {
  @apply bg-red-600 text-white hover:bg-red-700 active:bg-red-800;
}
.spinner {
  @apply inline-block h-4 w-4 border-2 border-current border-r-transparent rounded-full;
}
```

- [ ] **Step 5: Implement `index.ts`**

```ts
export * from "./Button";
```

- [ ] **Step 6: Run tests + coverage**

```bash
cd frontend && npm run test -- src/components/Button --coverage
```

Expected: 3 passed; 100% on `Button.tsx`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/Button/
git commit -m "feat(frontend): add Button primitive"
```

---

### Task H: `Callout`

**Files:**
- Create: `frontend/src/components/Callout/Callout.tsx`
- Create: `frontend/src/components/Callout/Callout.module.css`
- Create: `frontend/src/components/Callout/Callout.test.tsx`
- Create: `frontend/src/components/Callout/index.ts`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Callout } from "./Callout";

describe("Callout", () => {
  it("renders children with the variant data attr", () => {
    render(<Callout variant="error">Boom</Callout>);
    const el = screen.getByTestId("callout");
    expect(el).toHaveAttribute("data-variant", "error");
    expect(el).toHaveTextContent("Boom");
  });

  it("renders title and action button", async () => {
    const onClick = vi.fn();
    render(
      <Callout
        variant="warning"
        title="Heads up"
        action={{ label: "Retry", onClick }}
      >
        body text
      </Callout>,
    );
    expect(screen.getByText("Heads up")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("omits the action button when no action is provided", () => {
    render(<Callout variant="info">just text</Callout>);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `Callout.tsx`**

```tsx
import { ReactNode } from "react";
import styles from "./Callout.module.css";
import { Button } from "../Button";

export type CalloutProps = {
  variant: "info" | "warning" | "error";
  title?: ReactNode;
  children: ReactNode;
  action?: { label: string; onClick: () => void };
};

export function Callout({ variant, title, children, action }: CalloutProps) {
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      data-testid="callout"
      data-variant={variant}
      className={`${styles.callout} ${styles[variant]}`}
    >
      {title && <div className={styles.title}>{title}</div>}
      <div className={styles.body}>{children}</div>
      {action && (
        <div className={styles.action}>
          <Button variant="secondary" onClick={action.onClick}>
            {action.label}
          </Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Implement `Callout.module.css`**

```css
.callout {
  @apply rounded border-l-4 px-4 py-3 flex flex-col gap-2;
}
.title {
  @apply font-medium;
}
.body {
  @apply text-sm;
}
.action {
  @apply mt-1;
}
.info {
  @apply border-blue-500 bg-blue-50 text-blue-900;
}
.warning {
  @apply border-yellow-500 bg-yellow-50 text-yellow-900;
}
.error {
  @apply border-red-500 bg-red-50 text-red-900;
}
```

- [ ] **Step 4: `index.ts`**

```ts
export * from "./Callout";
```

- [ ] **Step 5: Run + coverage**

```bash
cd frontend && npm run test -- src/components/Callout --coverage
```

Expected: 3 passed; 100%.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/Callout/
git commit -m "feat(frontend): add Callout primitive"
```

---

### Task I: `EmptyState`

**Files:**
- Create: `frontend/src/components/EmptyState/EmptyState.tsx`
- Create: `frontend/src/components/EmptyState/EmptyState.module.css`
- Create: `frontend/src/components/EmptyState/EmptyState.test.tsx`
- Create: `frontend/src/components/EmptyState/index.ts`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("renders the message", () => {
    render(<EmptyState message="No projects yet." />);
    expect(screen.getByText("No projects yet.")).toBeInTheDocument();
  });

  it("renders and fires the action button when provided", async () => {
    const onClick = vi.fn();
    render(
      <EmptyState
        message="No projects yet."
        action={{ label: "Create project", onClick }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(onClick).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Implement `EmptyState.tsx`**

```tsx
import styles from "./EmptyState.module.css";
import { Button } from "../Button";

export type EmptyStateProps = {
  message: string;
  action?: { label: string; onClick: () => void };
};

export function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div className={styles.empty} data-testid="empty-state">
      <p className={styles.message}>{message}</p>
      {action && (
        <Button onClick={action.onClick}>{action.label}</Button>
      )}
    </div>
  );
}
```

- [ ] **Step 3: `EmptyState.module.css`**

```css
.empty {
  @apply flex flex-col items-center justify-center gap-3 py-12 text-center;
}
.message {
  @apply text-gray-600;
}
```

- [ ] **Step 4: `index.ts`**

```ts
export * from "./EmptyState";
```

- [ ] **Step 5: Run + commit**

```bash
cd frontend && npm run test -- src/components/EmptyState --coverage
git add frontend/src/components/EmptyState/
git commit -m "feat(frontend): add EmptyState primitive"
```

---

### Task J: `PageHeader`

**Files:**
- Create: `frontend/src/components/PageHeader/PageHeader.tsx`
- Create: `frontend/src/components/PageHeader/PageHeader.module.css`
- Create: `frontend/src/components/PageHeader/PageHeader.test.tsx`
- Create: `frontend/src/components/PageHeader/index.ts`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PageHeader } from "./PageHeader";

describe("PageHeader", () => {
  it("renders the title in an h1", () => {
    render(<PageHeader title="Projects" />);
    expect(screen.getByRole("heading", { level: 1, name: "Projects" })).toBeInTheDocument();
  });

  it("renders an action slot when provided", () => {
    render(<PageHeader title="Projects" action={<button>New</button>} />);
    expect(screen.getByRole("button", { name: "New" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement `PageHeader.tsx`**

```tsx
import { ReactNode } from "react";
import styles from "./PageHeader.module.css";

export type PageHeaderProps = {
  title: string;
  action?: ReactNode;
};

export function PageHeader({ title, action }: PageHeaderProps) {
  return (
    <div className={styles.header}>
      <h1 className={styles.title}>{title}</h1>
      {action && <div className={styles.action}>{action}</div>}
    </div>
  );
}
```

- [ ] **Step 3: `PageHeader.module.css`**

```css
.header {
  @apply flex items-center justify-between py-4 border-b border-gray-200;
}
.title {
  @apply text-3xl font-semibold;
}
.action {
  @apply flex items-center gap-2;
}
```

- [ ] **Step 4: `index.ts`**

```ts
export * from "./PageHeader";
```

- [ ] **Step 5: Run + commit**

```bash
cd frontend && npm run test -- src/components/PageHeader --coverage
git add frontend/src/components/PageHeader/
git commit -m "feat(frontend): add PageHeader primitive"
```

---

### Task K: `Table` + `TableSkeleton`

**Files:**
- Create: `frontend/src/components/Table/Table.tsx`
- Create: `frontend/src/components/Table/TableSkeleton.tsx`
- Create: `frontend/src/components/Table/Table.module.css`
- Create: `frontend/src/components/Table/Table.test.tsx`
- Create: `frontend/src/components/Table/index.ts`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Table, TableSkeleton } from "./index";

type Row = { id: string; name: string };
const columns = [
  { key: "name", header: "Name", cell: (r: Row) => r.name },
];

describe("Table", () => {
  it("renders rows", () => {
    render(<Table<Row> columns={columns} rows={[{ id: "1", name: "A" }]} rowKey={(r) => r.id} />);
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  it("renders the empty slot when there are no rows", () => {
    render(
      <Table<Row>
        columns={columns}
        rows={[]}
        rowKey={(r) => r.id}
        emptyState={<div data-testid="custom-empty">Nothing</div>}
      />,
    );
    expect(screen.getByTestId("custom-empty")).toBeInTheDocument();
  });

  it("renders skeleton rows when isLoading", () => {
    render(
      <Table<Row>
        columns={columns}
        rows={[]}
        rowKey={(r) => r.id}
        isLoading
      />,
    );
    expect(screen.getAllByTestId("skeleton-row")).toHaveLength(5);
  });
});

describe("TableSkeleton", () => {
  it("renders the requested number of rows", () => {
    render(<TableSkeleton columnCount={2} rowCount={3} />);
    expect(screen.getAllByTestId("skeleton-row")).toHaveLength(3);
  });
});
```

- [ ] **Step 2: Implement `Table.tsx`**

```tsx
import { ReactNode } from "react";
import styles from "./Table.module.css";
import { TableSkeleton } from "./TableSkeleton";

export type TableColumn<T> = {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  width?: string;
};

export type TableProps<T> = {
  columns: TableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  isLoading?: boolean;
  emptyState?: ReactNode;
};

export function Table<T>({ columns, rows, rowKey, isLoading, emptyState }: TableProps<T>) {
  if (isLoading) {
    return <TableSkeleton columnCount={columns.length} rowCount={5} />;
  }
  if (rows.length === 0 && emptyState) {
    return <>{emptyState}</>;
  }
  return (
    <table className={styles.table} data-testid="table">
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.key} style={c.width ? { width: c.width } : undefined}>
              {c.header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={rowKey(row)}>
            {columns.map((c) => (
              <td key={c.key}>{c.cell(row)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 3: Implement `TableSkeleton.tsx`**

```tsx
import styles from "./Table.module.css";

export type TableSkeletonProps = { columnCount: number; rowCount?: number };

export function TableSkeleton({ columnCount, rowCount = 5 }: TableSkeletonProps) {
  return (
    <table className={styles.table}>
      <tbody>
        {Array.from({ length: rowCount }).map((_, r) => (
          <tr key={r} data-testid="skeleton-row" className={styles.skeletonRow}>
            {Array.from({ length: columnCount }).map((__, c) => (
              <td key={c}><span className={styles.skeletonCell} /></td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: `Table.module.css`**

```css
.table {
  @apply w-full text-sm border-collapse;
}
.table th {
  @apply text-left font-medium px-3 h-10 border-b border-gray-200 bg-gray-50;
}
.table td {
  @apply px-3 h-10 border-b border-gray-100;
}
.table tr:hover td {
  @apply bg-gray-50;
}
.skeletonRow td {
  @apply py-2;
}
.skeletonCell {
  @apply block h-4 w-full bg-gray-100 rounded;
}
```

- [ ] **Step 5: `index.ts`**

```ts
export * from "./Table";
export * from "./TableSkeleton";
```

- [ ] **Step 6: Run + commit**

```bash
cd frontend && npm run test -- src/components/Table --coverage
git add frontend/src/components/Table/
git commit -m "feat(frontend): add Table + TableSkeleton primitives"
```

---

### Task L: `FormField` + `TextInput` + `Textarea`

**Files:**
- Create: `frontend/src/components/Form/FormField.tsx`
- Create: `frontend/src/components/Form/TextInput.tsx`
- Create: `frontend/src/components/Form/Textarea.tsx`
- Create: `frontend/src/components/Form/Form.module.css`
- Create: `frontend/src/components/Form/Form.test.tsx`
- Create: `frontend/src/components/Form/index.ts`

- [ ] **Step 1: Test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormField, TextInput, Textarea } from "./index";

describe("FormField + TextInput", () => {
  it("wires label, input, and error message", async () => {
    render(
      <FormField label="Name" htmlFor="name" error="already exists" required>
        <TextInput id="name" defaultValue="" />
      </FormField>,
    );
    const input = screen.getByLabelText(/Name/);
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAttribute("aria-describedby", "name-error");
    expect(screen.getByText("already exists")).toHaveAttribute("id", "name-error");
  });

  it("accepts typing", async () => {
    render(
      <FormField label="Name" htmlFor="name">
        <TextInput id="name" defaultValue="" />
      </FormField>,
    );
    await userEvent.type(screen.getByLabelText("Name"), "Alpha");
    expect(screen.getByLabelText("Name")).toHaveValue("Alpha");
  });
});

describe("Textarea", () => {
  it("renders multiline", async () => {
    render(<Textarea id="d" defaultValue="" />);
    await userEvent.type(screen.getByRole("textbox"), "x\ny");
    expect(screen.getByRole("textbox")).toHaveValue("x\ny");
  });
});
```

- [ ] **Step 2: Implement `FormField.tsx`**

```tsx
import { Children, cloneElement, isValidElement, ReactElement, ReactNode } from "react";
import styles from "./Form.module.css";

export type FormFieldProps = {
  label: string;
  htmlFor: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
};

export function FormField({ label, htmlFor, error, required, children }: FormFieldProps) {
  const errorId = `${htmlFor}-error`;
  const child = Children.only(children) as ReactElement<{
    "aria-invalid"?: boolean;
    "aria-describedby"?: string;
    "data-invalid"?: boolean;
  }>;
  const enhancedChild = isValidElement(child)
    ? cloneElement(child, {
        "aria-invalid": Boolean(error),
        "aria-describedby": error ? errorId : undefined,
        "data-invalid": Boolean(error),
      })
    : child;
  return (
    <div className={styles.field}>
      <label htmlFor={htmlFor} className={styles.label}>
        {label}
        {required && <span aria-hidden="true"> *</span>}
      </label>
      {enhancedChild}
      {error && (
        <p id={errorId} className={styles.error}>
          {error}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Implement `TextInput.tsx`**

```tsx
import { InputHTMLAttributes } from "react";
import styles from "./Form.module.css";

export type TextInputProps = InputHTMLAttributes<HTMLInputElement>;

export function TextInput(props: TextInputProps) {
  return <input type="text" className={styles.input} {...props} />;
}
```

- [ ] **Step 4: Implement `Textarea.tsx`**

```tsx
import { TextareaHTMLAttributes } from "react";
import styles from "./Form.module.css";

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea(props: TextareaProps) {
  return <textarea className={styles.textarea} {...props} />;
}
```

- [ ] **Step 5: `Form.module.css`**

```css
.field {
  @apply flex flex-col gap-1.5;
}
.label {
  @apply text-sm font-medium text-gray-900;
}
.input,
.textarea {
  @apply h-10 px-3 rounded border border-gray-300 bg-white text-sm;
}
.textarea {
  @apply h-auto py-2 min-h-[80px] resize-y;
}
.input[data-invalid="true"],
.textarea[data-invalid="true"] {
  @apply border-red-500;
}
.error {
  @apply text-sm text-red-700;
}
```

- [ ] **Step 6: `index.ts`**

```ts
export * from "./FormField";
export * from "./TextInput";
export * from "./Textarea";
```

- [ ] **Step 7: Run + commit**

```bash
cd frontend && npm run test -- src/components/Form --coverage
git add frontend/src/components/Form/
git commit -m "feat(frontend): add FormField + TextInput + Textarea primitives"
```
