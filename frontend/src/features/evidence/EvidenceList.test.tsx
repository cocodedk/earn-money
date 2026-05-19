import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { EvidenceList } from "./EvidenceList";

beforeEach(() => window.localStorage.clear());

const sampleEvidence = {
  id: "e1",
  scan_run: "r1",
  target: "t1abcdef",
  finding: null,
  source: "header.X-Powered-By",
  url: "https://dvwa.cocode.dk/",
  method: "GET",
  field: "X-Powered-By",
  matched_value: "PHP/7.4",
  raw_excerpt: null,
  content_hash: "ab",
  data: {},
  created_at: "2026-05-18T20:00:00.000000Z",
};

function withEvidence(rows: unknown[]) {
  server.use(
    msw.get("/api/evidence/", () =>
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
  );
}

describe("EvidenceList", () => {
  it("shows the skeleton while loading", () => {
    withEvidence([]);
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });

  it("renders an empty state when no evidence", async () => {
    withEvidence([]);
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    expect(await screen.findByText(/no evidence yet/i)).toBeInTheDocument();
  });

  it("renders rows with matched_value link to detail", async () => {
    withEvidence([sampleEvidence]);
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    const link = await screen.findByRole("link", { name: "PHP/7.4" });
    expect(link).toHaveAttribute("href", "/evidence/e1");
  });

  it("falls back to dashes for null url/method/field/matched_value in rows", async () => {
    withEvidence([
      { ...sampleEvidence, url: null, method: null, field: null, matched_value: null },
    ]);
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    await screen.findByText("header.X-Powered-By");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  it("renders text-input for source filter and select for project filter", async () => {
    withEvidence([]);
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    expect(
      (await screen.findByLabelText("Source")).tagName,
    ).toBe("INPUT");
    expect(screen.getByLabelText("Project").tagName).toBe("SELECT");
  });

  it("renders a callout with retry on fetch error", async () => {
    server.use(
      msw.get("/api/evidence/", () => HttpResponse.error()),
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/targets/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
    );
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
  });

  it("re-fetches when Retry is clicked", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/evidence/", () => {
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
    );
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    await screen.findByText(/backend unreachable/i);
    const first = calls;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(calls).toBeGreaterThan(first));
  });

  it("starts with filter values from URL search params", async () => {
    let lastUrl: URL | null = null;
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
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
    );
    renderWithProviders(<EvidenceList />, {
      route: "/evidence?source=body.html&scan_run=r1",
    });
    await waitFor(() => expect(lastUrl).not.toBeNull());
    expect(lastUrl!.searchParams.get("source")).toBe("body.html");
    expect(lastUrl!.searchParams.get("scan_run")).toBe("r1");
  });

  it("populates project/target/scan-run dropdowns and accepts source typing", async () => {
    server.use(
      msw.get("/api/evidence/", () =>
        HttpResponse.json({ count: 0, next: null, previous: null, results: [] }),
      ),
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "p1",
              name: "Lab",
              description: "",
              target_count: 1,
              scan_run_count: 1,
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
      msw.get("/api/targets/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "t1",
              project: "p1",
              base_url: "https://dvwa.cocode.dk",
              host: null,
              ip: null,
              status: "active",
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "r-abcdef12",
              project: "p1",
              stub_slug: "1.1",
              status: "done",
              target_run_count: 1,
              findings_count: 0,
              started_at: null,
              finished_at: null,
              created_at: "2026-05-18T20:00:00.000000Z",
            },
          ],
        }),
      ),
    );
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    expect(await screen.findByRole("option", { name: "Lab" })).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "https://dvwa.cocode.dk" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: /r-abcdef/ }),
    ).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Source"), "body");
    expect((screen.getByLabelText("Source") as HTMLInputElement).value).toBe(
      "body",
    );
    // Pick "All" — exercises onChange's delete branch when value is "".
    await userEvent.selectOptions(screen.getByLabelText("Project"), "");
    expect((screen.getByLabelText("Project") as HTMLSelectElement).value).toBe(
      "",
    );
  });
});
