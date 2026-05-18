import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../../test/server";
import { renderWithProviders } from "../../../test/renderWithProviders";
import { LifecycleControls } from "./LifecycleControls";
import type { ScanRun, ScanRunStatus } from "../../../types/api";

function run(status: ScanRunStatus): ScanRun {
  return {
    id: "r1",
    project: "p1",
    stub_slug: "1.1",
    status,
    target_run_count: 0,
    findings_count: 0,
    started_at: null,
    finished_at: null,
    created_at: "2026-05-18T20:00:00.000000Z",
  };
}

describe("LifecycleControls", () => {
  it("enables only Start when status is queued", () => {
    renderWithProviders(<LifecycleControls scanRun={run("queued")} />);
    expect(screen.getByRole("button", { name: "Start" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Pause" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Resume" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Stop" })).toBeDisabled();
  });

  it("enables Pause + Stop when running", () => {
    renderWithProviders(<LifecycleControls scanRun={run("running")} />);
    expect(screen.getByRole("button", { name: "Pause" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Stop" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Start" })).toBeDisabled();
  });

  it("enables Resume + Stop when paused", () => {
    renderWithProviders(<LifecycleControls scanRun={run("paused")} />);
    expect(screen.getByRole("button", { name: "Resume" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Stop" })).toBeEnabled();
  });

  it.each(["stopping", "stopped", "failed", "done"] as const)(
    "disables every button when status=%s",
    (status) => {
      renderWithProviders(<LifecycleControls scanRun={run(status)} />);
      ["Start", "Pause", "Resume", "Stop"].forEach((name) => {
        expect(screen.getByRole("button", { name })).toBeDisabled();
      });
    },
  );

  it("fires the start mutation when Start is clicked", async () => {
    let posted = false;
    server.use(
      msw.post("/api/scan-runs/r1/start/", () => {
        posted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithProviders(<LifecycleControls scanRun={run("queued")} />);
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => expect(posted).toBe(true));
  });
});
