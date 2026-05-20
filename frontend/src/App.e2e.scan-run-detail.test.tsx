import { describe, it, expect, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "./test/server";
import { renderWithProviders } from "./test/renderWithProviders";
import { makeStub } from "./features/stubs/__fixtures__/stub";
import { makeScanRun } from "./features/scan-runs/__fixtures__/scan-run";
import App from "./App";

beforeEach(() => window.localStorage.clear());

describe("end-to-end · scan-run detail", () => {
  it("opens the scan run detail page from the list and renders the header", async () => {
    const project = {
      id: "p-1",
      name: "Local Lab",
      description: "",
      target_count: 1,
      scan_run_count: 1,
      created_at: "2026-05-19T08:00:00.000000Z",
    };
    const run = makeScanRun({ id: "r-e2e" });
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({ count: 1, next: null, previous: null, results: [project] }),
      ),
      msw.get("/api/stubs/", () => HttpResponse.json([makeStub()])),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [run],
        }),
      ),
      msw.get("/api/scan-runs/r-e2e/", () => HttpResponse.json(run)),
    );

    renderWithProviders(<App />, { route: "/scan-runs" });

    await screen.findByTestId("status-queued");
    await userEvent.click(screen.getByRole("link", { name: "Open" }));
    expect(
      await screen.findByText(/Scan run · r-e2e/),
    ).toBeInTheDocument();
    expect(await screen.findByText("Local Lab")).toBeInTheDocument();
    expect(
      await screen.findByTestId("events-connection-status"),
    ).toBeInTheDocument();
  });
});
