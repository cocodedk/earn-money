# Phase 0 — Foundation

Install deps, configure Tailwind + Vitest + MSW. No application code yet. Each task ends with a commit.

---

### Task A: Install runtime + dev dependencies

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/package-lock.json`

- [ ] **Step 1: Install runtime deps**

```bash
cd frontend
npm install react-router-dom@^6.26.0 @tanstack/react-query@^5.51.0 @fontsource/inter@^5.0.0 @fontsource/jetbrains-mono@^5.0.0
```

- [ ] **Step 2: Install dev deps**

```bash
npm install -D tailwindcss@^3.4.0 postcss@^8.4.0 autoprefixer@^10.4.0 vitest@^2.0.0 @vitest/coverage-v8@^2.0.0 @testing-library/react@^16.0.0 @testing-library/jest-dom@^6.4.0 @testing-library/user-event@^14.5.0 jsdom@^25.0.0 msw@^2.4.0 @types/node@^20.0.0
```

- [ ] **Step 3: Verify package.json**

```bash
cat frontend/package.json | grep -E '"(react-router-dom|@tanstack/react-query|tailwindcss|vitest|msw)"'
```

Expected: all five lines printed.

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): install slice-1 deps (router, query, tailwind, vitest, msw)"
```

---

### Task B: Configure Tailwind + tokens

**Files:**
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/styles/global.css`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Create `tailwind.config.ts`**

```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx,css,module.css}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 2: Create `postcss.config.js`**

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 3: Create `src/styles/global.css`**

```css
@import "@fontsource/inter/400.css";
@import "@fontsource/inter/500.css";
@import "@fontsource/inter/600.css";
@import "@fontsource/jetbrains-mono/400.css";

@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color-scheme: light;
}

html,
body,
#root {
  height: 100%;
}

body {
  @apply bg-white text-gray-900 font-sans text-base antialiased;
}

*:focus-visible {
  @apply outline-none ring-2 ring-blue-500 ring-offset-1;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    transition-duration: 0ms !important;
    animation-duration: 0ms !important;
  }
}
```

- [ ] **Step 4: Import global.css from `src/main.tsx`**

Add at the top of `frontend/src/main.tsx`:

```tsx
import "./styles/global.css";
```

(Keep the rest of main.tsx unchanged for now.)

- [ ] **Step 5: Verify Tailwind compiles**

```bash
cd frontend && npx vite build
```

Expected: build succeeds, `dist/assets/index-*.css` exists.

- [ ] **Step 6: Commit**

```bash
git add frontend/tailwind.config.ts frontend/postcss.config.js frontend/src/styles/global.css frontend/src/main.tsx
git commit -m "chore(frontend): wire Tailwind v3 + self-hosted fonts"
```

---

### Task C: Configure Vitest + jsdom + coverage thresholds

**Files:**
- Modify: `frontend/vite.config.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/sanity.test.ts`
- Modify: `frontend/package.json` (add `test` script)

- [ ] **Step 1: Replace `vite.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    cors: true,
    hmr: { protocol: "ws", host: "localhost", port: 80, clientPort: 80 },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: { modules: { classNameStrategy: "non-scoped" } },
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/main.tsx",
        "src/**/*.test.{ts,tsx}",
        "src/test/**",
        "src/**/*.d.ts",
      ],
      thresholds: { lines: 100, branches: 100, functions: 100, statements: 100 },
    },
  },
});
```

- [ ] **Step 2: Create `src/test/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 3: Add a sanity test**

`frontend/src/sanity.test.ts`:

```ts
import { describe, it, expect } from "vitest";

describe("sanity", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
```

- [ ] **Step 4: Add the `test` script**

In `frontend/package.json` scripts:

```json
"test": "vitest run",
"test:watch": "vitest",
"test:coverage": "vitest run --coverage"
```

- [ ] **Step 5: Run tests**

```bash
cd frontend && npm run test
```

Expected: 1 passed, 0 failed.

- [ ] **Step 6: Delete the sanity test** (we don't keep throwaway tests)

```bash
rm frontend/src/sanity.test.ts
```

- [ ] **Step 7: Commit**

```bash
git add frontend/vite.config.ts frontend/src/test/setup.ts frontend/package.json
git commit -m "chore(frontend): configure vitest + jsdom + 100% coverage thresholds"
```

---

### Task D: Set up MSW server + per-test reset

**Files:**
- Create: `frontend/src/test/handlers.ts`
- Create: `frontend/src/test/server.ts`
- Create: `frontend/src/test/renderWithProviders.tsx`
- Modify: `frontend/src/test/setup.ts`

- [ ] **Step 1: Create empty handler array**

`frontend/src/test/handlers.ts`:

```ts
import { http, HttpResponse } from "msw";

// Per-task handlers; tests append via server.use() for happy / error paths.
export const handlers = [
  http.get("/api/health/", () =>
    HttpResponse.json({ status: "ok", db: true }),
  ),
];
```

- [ ] **Step 2: Create the test server**

`frontend/src/test/server.ts`:

```ts
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```

- [ ] **Step 3: Wire into `setup.ts`**

Replace `frontend/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

- [ ] **Step 4: Create the provider wrapper**

`frontend/src/test/renderWithProviders.tsx`:

```tsx
import { ReactElement, ReactNode } from "react";
import { render, RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

type Options = {
  route?: string;
  client?: QueryClient;
  renderOptions?: Omit<RenderOptions, "wrapper">;
};

export function renderWithProviders(ui: ReactElement, options: Options = {}) {
  const client =
    options.client ??
    new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[options.route ?? "/"]}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return { client, ...render(ui, { wrapper: Wrapper, ...options.renderOptions }) };
}
```

- [ ] **Step 5: Sanity-check the wiring with a one-off test**

`frontend/src/test/msw.sanity.test.ts`:

```ts
import { describe, it, expect } from "vitest";

describe("msw default handler", () => {
  it("returns the health payload", async () => {
    const response = await fetch("/api/health/");
    expect(response.ok).toBe(true);
    expect(await response.json()).toEqual({ status: "ok", db: true });
  });
});
```

- [ ] **Step 6: Run the sanity test**

```bash
cd frontend && npm run test -- src/test/msw.sanity.test.ts
```

Expected: 1 passed.

- [ ] **Step 7: Delete the sanity test**

```bash
rm frontend/src/test/msw.sanity.test.ts
```

- [ ] **Step 8: Commit**

```bash
git add frontend/src/test/
git commit -m "chore(frontend): wire MSW server + renderWithProviders helper"
```
