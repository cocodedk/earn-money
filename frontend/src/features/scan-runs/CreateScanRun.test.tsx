import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { CreateScanRun } from "./CreateScanRun";

beforeEach(() => window.localStorage.clear());

function LocationProbe() {
  return <span data-testid="loc">{useLocation().pathname}</span>;
}

const sampleTargets = [
  {
    id: "t1",
    project: "p1",
    base_url: "https://dvwa.cocode.dk",
    host: null,
    ip: null,
    status: "active",
    created_at: "2026-05-18T20:00:00.000000Z",
  },
  {
    id: "t2",
    project: "p1",
    base_url: "https://webgoat.cocode.dk",
    host: null,
    ip: null,
    status: "active",
    created_at: "2026-05-18T20:00:00.000000Z",
  },
  {
    id: "t3",
    project: "p1",
    base_url: "https://retired.cocode.dk",
    host: null,
    ip: null,
    status: "retired",
    created_at: "2026-05-18T20:00:00.000000Z",
  },
];

const sampleStubs = [
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
];

function withProjectStubsAndTargets() {
  window.localStorage.setItem("em.frontend.currentProjectId", "p1");
  server.use(
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
            target_count: 3,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
        ],
      }),
    ),
    msw.get("/api/targets/", () =>
      HttpResponse.json({
        count: sampleTargets.length,
        next: null,
        previous: null,
        results: sampleTargets,
      }),
    ),
    msw.get("/api/stubs/", () => HttpResponse.json(sampleStubs)),
  );
}

describe("CreateScanRun", () => {
  it("blocks when no current project is set", () => {
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    expect(screen.getByText(/select a project/i)).toBeInTheDocument();
  });

  it("defaults to selecting all active targets", async () => {
    withProjectStubsAndTargets();
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await screen.findByText("https://dvwa.cocode.dk");
    const dvwa = screen.getByRole("checkbox", {
      name: "https://dvwa.cocode.dk",
    });
    const webgoat = screen.getByRole("checkbox", {
      name: "https://webgoat.cocode.dk",
    });
    expect(dvwa).toBeChecked();
    expect(webgoat).toBeChecked();
  });

  it("omits retired targets from the list", async () => {
    withProjectStubsAndTargets();
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await screen.findByText("https://dvwa.cocode.dk");
    expect(screen.queryByText("https://retired.cocode.dk")).not.toBeInTheDocument();
  });

  it("validates at least one target must be selected", async () => {
    withProjectStubsAndTargets();
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await userEvent.click(
      await screen.findByRole("button", { name: "Clear all" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    expect(
      await screen.findByText(/at least one target is required/i),
    ).toBeInTheDocument();
  });

  it("submits and routes to /scan-runs/<id>", async () => {
    withProjectStubsAndTargets();
    let received: { project: string; stub_slug: string; target_ids: string[] } | null = null;
    server.use(
      msw.post("/api/scan-runs/", async ({ request }) => {
        received = (await request.json()) as typeof received;
        return HttpResponse.json(
          {
            id: "r-new",
            project: "p1",
            stub_slug: "1.1",
            status: "queued",
            target_run_count: 2,
            findings_count: 0,
            started_at: null,
            finished_at: null,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    renderWithProviders(
      <>
        <CreateScanRun />
        <LocationProbe />
      </>,
      { route: "/scan-runs/new" },
    );
    await screen.findByText("https://dvwa.cocode.dk");
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/scan-runs/r-new"),
    );
    expect(received!.project).toBe("p1");
    expect(received!.stub_slug).toBe("1.1");
    expect(received!.target_ids).toEqual(["t1", "t2"]);
  });

  it("Create-and-start fires the start lifecycle after create", async () => {
    withProjectStubsAndTargets();
    let started = false;
    server.use(
      msw.post("/api/scan-runs/", () =>
        HttpResponse.json(
          {
            id: "r-new",
            project: "p1",
            stub_slug: "1.1",
            status: "queued",
            target_run_count: 2,
            findings_count: 0,
            started_at: null,
            finished_at: null,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        ),
      ),
      msw.post("/api/scan-runs/r-new/start/", () => {
        started = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithProviders(
      <>
        <CreateScanRun />
        <LocationProbe />
      </>,
      { route: "/scan-runs/new" },
    );
    await screen.findByText("https://dvwa.cocode.dk");
    await userEvent.click(
      screen.getByRole("button", { name: "Create and start" }),
    );
    await waitFor(() => expect(started).toBe(true));
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/scan-runs/r-new"),
    );
  });

  it("renders generic message on 5xx", async () => {
    withProjectStubsAndTargets();
    server.use(
      msw.post("/api/scan-runs/", () => HttpResponse.json({}, { status: 503 })),
    );
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await screen.findByText("https://dvwa.cocode.dk");
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    expect(
      await screen.findByText(/something went wrong/i),
    ).toBeInTheDocument();
  });

  it("renders backend unreachable on network failure", async () => {
    withProjectStubsAndTargets();
    server.use(msw.post("/api/scan-runs/", () => HttpResponse.error()));
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await screen.findByText("https://dvwa.cocode.dk");
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
  });

  it("renders non_field_errors banner", async () => {
    withProjectStubsAndTargets();
    server.use(
      msw.post("/api/scan-runs/", () =>
        HttpResponse.json({ non_field_errors: ["bad combo"] }, { status: 400 }),
      ),
    );
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await screen.findByText("https://dvwa.cocode.dk");
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    expect(await screen.findByText("bad combo")).toBeInTheDocument();
  });

  it("renders detail banner on non-validation 4xx", async () => {
    withProjectStubsAndTargets();
    server.use(
      msw.post("/api/scan-runs/", () =>
        HttpResponse.json({ detail: "Forbidden." }, { status: 403 }),
      ),
    );
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await screen.findByText("https://dvwa.cocode.dk");
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    expect(await screen.findByText("Forbidden.")).toBeInTheDocument();
  });

  it("renders generic banner for field-keyed 400 (no per-field renderer)", async () => {
    withProjectStubsAndTargets();
    server.use(
      msw.post("/api/scan-runs/", () =>
        HttpResponse.json({ stub_slug: ["unknown stub"] }, { status: 400 }),
      ),
    );
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await screen.findByText("https://dvwa.cocode.dk");
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    expect(
      await screen.findByText(/could not create scan run/i),
    ).toBeInTheDocument();
  });

  it("toggles individual targets", async () => {
    withProjectStubsAndTargets();
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    const dvwa = await screen.findByRole("checkbox", {
      name: "https://dvwa.cocode.dk",
    });
    await userEvent.click(dvwa);
    expect(dvwa).not.toBeChecked();
    await userEvent.click(dvwa);
    expect(dvwa).toBeChecked();
  });

  it("Select all re-checks every target", async () => {
    withProjectStubsAndTargets();
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await userEvent.click(
      await screen.findByRole("button", { name: "Clear all" }),
    );
    await userEvent.click(screen.getByRole("button", { name: "Select all" }));
    expect(
      screen.getByRole("checkbox", { name: "https://dvwa.cocode.dk" }),
    ).toBeChecked();
  });

  it("changes stub_slug when the dropdown is updated", async () => {
    window.localStorage.setItem("em.frontend.currentProjectId", "p1");
    server.use(
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
              scan_run_count: 0,
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
      msw.get("/api/stubs/", () =>
        HttpResponse.json([
          { ...sampleStubs[0] },
          { ...sampleStubs[0], slug: "1.2", title: "Server headers" },
        ]),
      ),
    );
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await screen.findByRole("option", { name: /1\.2/ });
    const select = screen.getByLabelText("Stub") as HTMLSelectElement;
    await userEvent.selectOptions(select, "1.2");
    expect(select.value).toBe("1.2");
  });
});
