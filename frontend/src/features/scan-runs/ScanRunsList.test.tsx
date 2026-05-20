import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { LocationProbe, withPaginated } from "../../test/helpers";
import { withBareArray } from "../../test/helpers";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeStub } from "../stubs/__fixtures__/stub";
import { ScanRunsList } from "./ScanRunsList";

const PROJECT = {
  id: "p-1",
  name: "Local Lab",
  description: "",
  target_count: 1,
  scan_run_count: 1,
  created_at: "2026-05-19T08:00:00.000000Z",
};

function withDeps() {
  withPaginated("/api/projects/", [PROJECT]);
  withBareArray("/api/stubs/", [makeStub()]);
}

describe("ScanRunsList — state branches", () => {
  it("shows a skeleton while loading", () => {
    withDeps();
    withPaginated("/api/scan-runs/", []);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });

  it("shows the empty state with Create scan run that navigates", async () => {
    withDeps();
    withPaginated("/api/scan-runs/", []);
    renderWithProviders(
      <>
        <ScanRunsList />
        <LocationProbe />
      </>,
      { route: "/scan-runs" },
    );
    expect(await screen.findByText("No scan runs yet.")).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/scan-runs/new"),
    );
  });

  it("shows a Backend-unreachable callout with Retry on fetch error", async () => {
    withDeps();
    server.use(msw.get("/api/scan-runs/", () => HttpResponse.error()));
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    expect(
      await screen.findByText(/backend unreachable/i),
    ).toBeInTheDocument();
    let calls = 0;
    server.use(
      msw.get("/api/scan-runs/", () => {
        calls += 1;
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(calls).toBeGreaterThan(0));
  });

  it("renders a row joined with project name and stub slug", async () => {
    withDeps();
    withPaginated("/api/scan-runs/", [makeScanRun()]);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    expect(
      await screen.findByRole("cell", { name: "Local Lab" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "1.1" })).toBeInTheDocument();
    expect(screen.getByTestId("status-queued")).toBeInTheDocument();
  });

  it("renders the short ID and the Open link to the detail route", async () => {
    withDeps();
    withPaginated("/api/scan-runs/", [
      makeScanRun({ id: "abc12345-defg-hijk-lmno-pqrstuvwxyz0" }),
    ]);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    expect(await screen.findByText("abc12345")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open" })).toHaveAttribute(
      "href",
      "/scan-runs/abc12345-defg-hijk-lmno-pqrstuvwxyz0",
    );
  });
});

describe("ScanRunsList — state-machine action buttons", () => {
  const cases = [
    { status: "queued", visible: ["Start"], hidden: ["Pause", "Resume", "Stop"] },
    { status: "running", visible: ["Pause", "Stop"], hidden: ["Start", "Resume"] },
    { status: "paused", visible: ["Resume", "Stop"], hidden: ["Start", "Pause"] },
    { status: "stopping", visible: [], hidden: ["Start", "Pause", "Resume", "Stop"] },
    { status: "stopped", visible: [], hidden: ["Start", "Pause", "Resume", "Stop"] },
    { status: "failed", visible: [], hidden: ["Start", "Pause", "Resume", "Stop"] },
    { status: "done", visible: [], hidden: ["Start", "Pause", "Resume", "Stop"] },
  ] as const;

  it.each(cases)(
    "$status row shows only [$visible] action buttons",
    async ({ status, visible, hidden }) => {
      withDeps();
      withPaginated("/api/scan-runs/", [makeScanRun({ status })]);
      renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
      await screen.findByTestId(`status-${status}`);
      for (const label of visible) {
        expect(
          screen.getByRole("button", { name: label }),
        ).toBeInTheDocument();
      }
      for (const label of hidden) {
        expect(
          screen.queryByRole("button", { name: label }),
        ).not.toBeInTheDocument();
      }
    },
  );

  it("renders timestamps in the started_at/finished_at columns when present", async () => {
    withDeps();
    withPaginated("/api/scan-runs/", [
      makeScanRun({
        status: "done",
        started_at: "2026-05-19T09:00:00.123456Z",
        finished_at: "2026-05-19T09:05:30.654321Z",
      }),
    ]);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    await screen.findByTestId("status-done");
    expect(screen.getByText("2026-05-19T09:00:00")).toBeInTheDocument();
    expect(screen.getByText("2026-05-19T09:05:30")).toBeInTheDocument();
  });

  it("falls back to short UUIDs for unknown project and raw slug for unknown stub", async () => {
    withDeps();
    withPaginated("/api/scan-runs/", [
      makeScanRun({
        project: "p-unknown-abcd-ef01-2345-6789abcdef01",
        stub_slug: "99.99",
      }),
    ]);
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    expect(await screen.findByText("p-unknow")).toBeInTheDocument();
    expect(screen.getByText("99.99")).toBeInTheDocument();
  });

  it.each(["pause", "resume", "stop"] as const)(
    "%s click fires the corresponding mutation",
    async (action) => {
      const runningStates = {
        pause: "running",
        resume: "paused",
        stop: "running",
      } as const;
      const label = action.charAt(0).toUpperCase() + action.slice(1);
      withDeps();
      let hit = false;
      server.use(
        msw.get("/api/scan-runs/", () =>
          HttpResponse.json({
            count: 1,
            next: null,
            previous: null,
            results: [makeScanRun({ status: runningStates[action] })],
          }),
        ),
        msw.post(`/api/scan-runs/r-1/${action}/`, () => {
          hit = true;
          return HttpResponse.json(
            makeScanRun({ status: action === "stop" ? "stopping" : "running" }),
          );
        }),
      );
      renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
      await screen.findByTestId(`status-${runningStates[action]}`);
      await userEvent.click(screen.getByRole("button", { name: label }));
      await waitFor(() => expect(hit).toBe(true));
    },
  );

  it("clicking Start fires the mutation and the row flips to running on refetch", async () => {
    withDeps();
    let status: "queued" | "running" = "queued";
    server.use(
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json({
          count: 1,
          next: null,
          previous: null,
          results: [makeScanRun({ status })],
        }),
      ),
      msw.post("/api/scan-runs/r-1/start/", () => {
        status = "running";
        return HttpResponse.json(makeScanRun({ status: "running" }));
      }),
    );
    renderWithProviders(<ScanRunsList />, { route: "/scan-runs" });
    await screen.findByTestId("status-queued");
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() =>
      expect(screen.getByTestId("status-running")).toBeInTheDocument(),
    );
  });
});
