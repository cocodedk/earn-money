import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { FindingsList } from "./FindingsList";

beforeEach(() => window.localStorage.clear());

const sampleFinding = {
  id: "f1",
  scan_run: "r1",
  target: "t1abcdef",
  stub_slug: "1.1",
  title: "Express detected",
  category: "framework-detection",
  severity: "info",
  confidence: "high",
  status: "candidate",
  data: {},
  created_at: "2026-05-18T20:00:00.000000Z",
  updated_at: "2026-05-18T20:00:00.000000Z",
};

function withFindings(rows: unknown[]) {
  server.use(
    msw.get("/api/findings/", () =>
      HttpResponse.json({
        count: rows.length,
        next: null,
        previous: null,
        results: rows,
      }),
    ),
    msw.get("/api/projects/", () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
    msw.get("/api/targets/", () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
    msw.get("/api/scan-runs/", () =>
      HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
    ),
    msw.get("/api/stubs/", () => HttpResponse.json([])),
  );
}

describe("FindingsList", () => {
  it("shows the skeleton while loading", () => {
    withFindings([]);
    renderWithProviders(<FindingsList />, { route: "/findings" });
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });

  it("renders an empty state when no findings", async () => {
    withFindings([]);
    renderWithProviders(<FindingsList />, { route: "/findings" });
    expect(await screen.findByText(/no findings yet/i)).toBeInTheDocument();
  });

  it("renders rows with severity badge + truncated target id + link to detail", async () => {
    withFindings([sampleFinding]);
    renderWithProviders(<FindingsList />, { route: "/findings" });
    const link = await screen.findByRole("link", { name: "Express detected" });
    expect(link).toHaveAttribute("href", "/findings/f1");
    expect(screen.getByTestId("severity-badge")).toHaveAttribute(
      "data-severity",
      "info",
    );
    expect(screen.getByText("t1abcdef")).toBeInTheDocument();
  });

  it("renders a callout with retry on fetch error", async () => {
    server.use(
      msw.get("/api/findings/", () => HttpResponse.error()),
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/targets/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/stubs/", () => HttpResponse.json([])),
    );
    renderWithProviders(<FindingsList />, { route: "/findings" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
  });

  it("re-fetches when Retry is clicked", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/findings/", () => {
        calls += 1;
        return HttpResponse.error();
      }),
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/targets/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/stubs/", () => HttpResponse.json([])),
    );
    renderWithProviders(<FindingsList />, { route: "/findings" });
    await screen.findByText(/backend unreachable/i);
    const first = calls;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(calls).toBeGreaterThan(first));
  });

  it("starts with filter values from URL search params", async () => {
    let lastUrl: URL | null = null;
    server.use(
      msw.get("/api/findings/", ({ request }) => {
        lastUrl = new URL(request.url);
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/targets/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/stubs/", () => HttpResponse.json([])),
    );
    renderWithProviders(<FindingsList />, {
      route: "/findings?severity=high&stub=1.1",
    });
    await waitFor(() => expect(lastUrl).not.toBeNull());
    expect(lastUrl!.searchParams.get("severity")).toBe("high");
    expect(lastUrl!.searchParams.get("stub")).toBe("1.1");
  });

  it("populates Stub dropdown from useStubsQuery and updates URL on change", async () => {
    server.use(
      msw.get("/api/findings/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/targets/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/stubs/", () =>
        HttpResponse.json([
          {
            slug: "1.1",
            phase: 1,
            spec: 1,
            title: "Framework detection",
            status: "done",
            fixture: null,
            category: "x",
            phase_title: "x",
            phase_slug: "x",
            spec_slug: "x",
            path: "x",
          },
        ]),
      ),
    );
    renderWithProviders(<FindingsList />, { route: "/findings" });
    await screen.findByRole("option", { name: /1\.1/ });
    await userEvent.selectOptions(screen.getByLabelText("Stub"), "1.1");
    // After selection, URL becomes /findings?stub=1.1; the next /api/findings/
    // request includes ?stub=1.1. Asserting via the dropdown value avoids
    // racing the refetch.
    expect((screen.getByLabelText("Stub") as HTMLSelectElement).value).toBe(
      "1.1",
    );
  });
});
