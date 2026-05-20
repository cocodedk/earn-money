# Phase 4 — StubDetail page

Detail page over `/api/stubs/<slug>/`. Markdown body rendered in `<pre>` per 14-styling — no markdown-renderer dep. 404 branch surfaces "Stub not found." with a back link.

---

### Task D: `StubDetail` page

**Files:**
- Create: `frontend/src/features/stubs/StubDetail.tsx`
- Create: `frontend/src/features/stubs/StubDetail.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/features/stubs/StubDetail.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { StubDetail } from "./StubDetail";

function renderAt(path: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/stubs/:slug" element={<StubDetail />} />
    </Routes>,
    { route: path },
  );
}

const FULL = {
  slug: "1.1",
  phase: 1,
  spec: 1,
  phase_slug: "01-information-gathering",
  spec_slug: "framework-detection",
  title: "Framework detection",
  phase_title: "Information gathering",
  category: "Content discovery",
  status: "done" as const,
  fixture: "juice-shop",
  path: "01-information-gathering/01-framework-detection.md",
  body: "# 1.1 Framework detection\n\nDetect the application framework.",
};

describe("StubDetail", () => {
  it("renders the title, metadata, and the markdown body", async () => {
    server.use(msw.get("/api/stubs/1.1/", () => HttpResponse.json(FULL)));
    renderAt("/stubs/1.1");
    expect(
      await screen.findByText(/1\.1 · Framework detection/),
    ).toBeInTheDocument();
    expect(screen.getByText("Information gathering")).toBeInTheDocument();
    expect(screen.getByText("Content discovery")).toBeInTheDocument();
    expect(screen.getByTestId("status-done")).toBeInTheDocument();
    expect(screen.getByText(/Detect the application framework/)).toBeInTheDocument();
  });

  it("renders an em-dash when spec_slug is empty", async () => {
    server.use(
      msw.get("/api/stubs/1.1/", () =>
        HttpResponse.json({ ...FULL, spec_slug: "" }),
      ),
    );
    renderAt("/stubs/1.1");
    expect(await screen.findByText("—")).toBeInTheDocument();
  });

  it("renders Stub not found on 404 with a back link", async () => {
    server.use(
      msw.get("/api/stubs/9.9/", () =>
        HttpResponse.json({ detail: "No stub" }, { status: 404 }),
      ),
    );
    renderAt("/stubs/9.9");
    expect(await screen.findByText(/stub not found/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /back to stubs/i }),
    ).toHaveAttribute("href", "/stubs");
  });

  it("renders a Backend-unreachable callout on transport error", async () => {
    server.use(msw.get("/api/stubs/1.1/", () => HttpResponse.error()));
    renderAt("/stubs/1.1");
    expect(
      await screen.findByText(/backend unreachable/i),
    ).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test — it must fail**

```bash
cd frontend && npm test -- src/features/stubs/StubDetail
```

Expected: module-not-found.

- [ ] **Step 3: Implement `StubDetail.tsx`**

```tsx
import { Link, useParams } from "react-router-dom";
import { ROUTES } from "../../app/routes";
import { PageHeader } from "../../components/PageHeader";
import { Callout } from "../../components/Callout";
import { HttpError } from "../../lib/http";
import { useStubQuery } from "./api";
import type { Stub, StubStatus } from "../../types/api";

const STATUS_PALETTE: Record<StubStatus, string> = {
  done: "bg-green-100 text-green-800",
  "in-progress": "bg-blue-100 text-blue-800",
  blocked: "bg-amber-100 text-amber-800",
  pending: "bg-gray-200 text-gray-700",
};

function StatusBadge({ status }: { status: StubStatus }) {
  return (
    <span
      data-testid={`status-${status}`}
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${STATUS_PALETTE[status]}`}
    >
      {status}
    </span>
  );
}

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4 text-sm">
      <span className="w-32 font-medium text-gray-600">{label}</span>
      <span>{children}</span>
    </div>
  );
}

function StubBody({ stub }: { stub: Stub }) {
  return (
    <>
      <PageHeader title={`${stub.slug} · ${stub.title}`} />
      <div className="mt-4 flex flex-col gap-2">
        <MetaRow label="Phase">{stub.phase_title}</MetaRow>
        <MetaRow label="Category">{stub.category || "—"}</MetaRow>
        <MetaRow label="Spec slug">{stub.spec_slug || "—"}</MetaRow>
        <MetaRow label="Status"><StatusBadge status={stub.status} /></MetaRow>
        <MetaRow label="Fixture">{stub.fixture}</MetaRow>
        <MetaRow label="Path"><code>{stub.path}</code></MetaRow>
      </div>
      <pre
        role="article"
        className="mt-6 whitespace-pre-wrap font-mono text-sm bg-gray-50 p-4 rounded border border-gray-200"
      >
        {stub.body}
      </pre>
    </>
  );
}

export function StubDetail() {
  const { slug } = useParams();
  const query = useStubQuery(slug);

  if (query.error instanceof HttpError && query.error.response.status === 404) {
    return (
      <>
        <PageHeader title="Stub not found" />
        <div className="mt-4">
          <Callout variant="info">
            No stub matches "{slug}".{" "}
            <Link to={ROUTES.stubs}>Back to stubs.</Link>
          </Callout>
        </div>
      </>
    );
  }
  if (query.isError) {
    return (
      <>
        <PageHeader title="Stub" />
        <div className="mt-4">
          <Callout variant="error" title="Backend unreachable">
            Could not load stub.
          </Callout>
        </div>
      </>
    );
  }
  if (!query.data) {
    // Loading branch — show the header skeleton.
    return <PageHeader title="Loading…" />;
  }
  return <StubBody stub={query.data} />;
}
```

The file lands around 90 lines; well under the 200-line cap.

- [ ] **Step 4: Run + verify**

```bash
cd frontend && npm test -- src/features/stubs/StubDetail --coverage
```

Expected: 4 tests pass; 100% coverage on `StubDetail.tsx`. If coverage flags the loading branch as untested, add a 5th test:

```tsx
it("shows a loading header before data resolves", async () => {
  server.use(msw.get("/api/stubs/1.1/", () => new Promise(() => {})));
  renderAt("/stubs/1.1");
  expect(await screen.findByText("Loading…")).toBeInTheDocument();
});
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stubs/StubDetail.tsx frontend/src/features/stubs/StubDetail.test.tsx
git commit -m "feat(frontend): add StubDetail with markdown body, 404 branch, status badge"
```
