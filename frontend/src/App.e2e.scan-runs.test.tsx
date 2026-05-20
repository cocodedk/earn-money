import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "./test/server";
import { renderWithProviders } from "./test/renderWithProviders";
import { makeStub } from "./features/stubs/__fixtures__/stub";
import { makeScanRun } from "./features/scan-runs/__fixtures__/scan-run";
import App from "./App";

beforeEach(() => window.localStorage.clear());

describe("end-to-end · scan-runs", () => {
  it("creates a scan run via the form and lands on a populated list", async () => {
    const project = {
      id: "p-1",
      name: "Local Lab",
      description: "",
      target_count: 1,
      scan_run_count: 0,
      created_at: "2026-05-19T08:00:00.000000Z",
    };
    const target = {
      id: "t-1",
      project: "p-1",
      base_url: "https://dvwa.cocode.dk",
      host: "dvwa.cocode.dk",
      ip: null,
      status: "active" as const,
      created_at: "2026-05-19T08:00:00.000000Z",
      updated_at: "2026-05-19T08:00:00.000000Z",
    };
    let stored: ReturnType<typeof makeScanRun> | null = null;
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [project] }),
      ),
      msw.get("/api/targets/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [target] }),
      ),
      msw.get("/api/stubs/", () => HttpResponse.json([makeStub()])),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json({
          count: stored ? 1 : 0,
          next: null,
          previous: null,
          results: stored ? [stored] : [],
        }),
      ),
      msw.post("/api/scan-runs/", async () => {
        stored = makeScanRun({ id: "r-e2e" });
        return HttpResponse.json(stored, { status: 201 });
      }),
    );

    renderWithProviders(<App />, { route: "/scan-runs/new" });

    const projectSelect = await screen.findByLabelText(/Project/);
    await waitFor(() => expect(projectSelect).not.toBeDisabled());
    await userEvent.selectOptions(projectSelect, "Local Lab");
    const stubSelect = await screen.findByLabelText(/Stub/);
    await waitFor(() => expect(stubSelect).not.toBeDisabled());
    await userEvent.selectOptions(stubSelect, "1.1 · Framework detection");
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );

    await waitFor(() =>
      expect(screen.getByText("Scan runs")).toBeInTheDocument(),
    );
    expect(await screen.findByTestId("status-queued")).toBeInTheDocument();
  });
});
