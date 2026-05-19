import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { LocationProbe, withBareArray, withPaginated } from "../../test/helpers";
import { makeStub } from "../stubs/__fixtures__/stub";
import { makeScanRun } from "./__fixtures__/scan-run";
import { CreateScanRun } from "./CreateScanRun";

const PROJECT = {
  id: "p-1",
  name: "Local Lab",
  description: "",
  target_count: 1,
  scan_run_count: 0,
  created_at: "2026-05-19T08:00:00.000000Z",
};

const TARGET_ACTIVE = {
  id: "t-1",
  project: "p-1",
  base_url: "https://dvwa.cocode.dk",
  host: "dvwa.cocode.dk",
  ip: null,
  status: "active" as const,
  created_at: "2026-05-19T08:00:00.000000Z",
  updated_at: "2026-05-19T08:00:00.000000Z",
};

const TARGET_RETIRED = {
  ...TARGET_ACTIVE,
  id: "t-2",
  base_url: "https://retired.cocode.dk",
  host: "retired.cocode.dk",
  status: "retired" as const,
};

function withDeps(
  overrides: {
    projects?: unknown[];
    stubs?: unknown[];
    targets?: unknown[];
  } = {},
) {
  withPaginated("/api/projects/", overrides.projects ?? [PROJECT]);
  withBareArray("/api/stubs/", overrides.stubs ?? [makeStub()]);
  withPaginated("/api/targets/", overrides.targets ?? [TARGET_ACTIVE]);
}

async function pickProject() {
  const select = await screen.findByLabelText(/Project/);
  await waitFor(() => expect(select).not.toBeDisabled());
  await userEvent.selectOptions(select, "Local Lab");
}

async function pickStub() {
  const select = await screen.findByLabelText(/Stub/);
  await waitFor(() => expect(select).not.toBeDisabled());
  await userEvent.selectOptions(select, "1.1 · Framework detection");
}

describe("CreateScanRun — happy paths", () => {
  it("creates a run with all active project targets and navigates to /scan-runs", async () => {
    withDeps({ targets: [TARGET_ACTIVE, TARGET_RETIRED] });
    let received: { target_ids?: string[] } = {};
    server.use(
      msw.post("/api/scan-runs/", async ({ request }) => {
        received = (await request.json()) as typeof received;
        return HttpResponse.json(makeScanRun(), { status: 201 });
      }),
    );
    renderWithProviders(
      <>
        <CreateScanRun />
        <LocationProbe />
      </>,
      { route: "/scan-runs/new" },
    );
    await pickProject();
    await pickStub();
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/scan-runs"),
    );
    expect(received.target_ids).toEqual(["t-1"]);
  });

  it("creates and starts (two-leg) on the Create-and-start button", async () => {
    withDeps();
    let createCalls = 0;
    let startCalls = 0;
    server.use(
      msw.post("/api/scan-runs/", () => {
        createCalls += 1;
        return HttpResponse.json(makeScanRun({ id: "r-new" }), { status: 201 });
      }),
      msw.post("/api/scan-runs/r-new/start/", () => {
        startCalls += 1;
        return HttpResponse.json(makeScanRun({ status: "running" }));
      }),
    );
    renderWithProviders(
      <>
        <CreateScanRun />
        <LocationProbe />
      </>,
      { route: "/scan-runs/new" },
    );
    await pickProject();
    await pickStub();
    await userEvent.click(
      screen.getByRole("button", { name: "Create and start" }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/scan-runs"),
    );
    expect(createCalls).toBe(1);
    expect(startCalls).toBe(1);
  });

  it("keeps the queued run and shows inline error when the start leg fails", async () => {
    withDeps();
    server.use(
      msw.post("/api/scan-runs/", () =>
        HttpResponse.json(makeScanRun({ id: "r-queued" }), { status: 201 }),
      ),
      msw.post("/api/scan-runs/r-queued/start/", () =>
        HttpResponse.json({ detail: "Illegal transition." }, { status: 400 }),
      ),
    );
    renderWithProviders(
      <>
        <CreateScanRun />
        <LocationProbe />
      </>,
      { route: "/scan-runs/new" },
    );
    await pickProject();
    await pickStub();
    await userEvent.click(
      screen.getByRole("button", { name: "Create and start" }),
    );
    // Inline start-leg error stays visible; we don't navigate away,
    // so the operator sees the error. The queued row is already in
    // the list (peer's micro-nit) and the row's Start button retries.
    expect(
      await screen.findByText(/Illegal transition\./),
    ).toBeInTheDocument();
    expect(screen.getByTestId("loc").textContent).toBe("/scan-runs/new");
  });
});

describe("CreateScanRun — projects/stubs/targets gating", () => {
  it("shows the Create-a-project link when no projects exist", async () => {
    withDeps({ projects: [] });
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    const link = await screen.findByRole("link", {
      name: /create a project first/i,
    });
    expect(link).toHaveAttribute("href", "/projects/new");
  });

  it("renders Could not load stubs when stubs query errors", async () => {
    withPaginated("/api/projects/", [PROJECT]);
    withPaginated("/api/targets/", [TARGET_ACTIVE]);
    server.use(msw.get("/api/stubs/", () => HttpResponse.error()));
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    expect(
      await screen.findByText(/could not load stubs/i),
    ).toBeInTheDocument();
  });

  it("shows an info message when the picked project has no active targets", async () => {
    withDeps({ targets: [TARGET_RETIRED] });
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await pickProject();
    await pickStub();
    expect(
      await screen.findByText(/no active targets/i),
    ).toBeInTheDocument();
  });
});

describe("CreateScanRun — validation", () => {
  it("requires project, stub, and at least one target", async () => {
    withDeps();
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    expect(
      await screen.findByText(/project is required/i),
    ).toBeInTheDocument();
  });

  it("requires stub when project is set but stub is not", async () => {
    withDeps();
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await pickProject();
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    expect(
      await screen.findByText(/stub is required/i),
    ).toBeInTheDocument();
  });

  it("toggleSelected adds then removes a target id when clicked twice", async () => {
    withDeps();
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await pickProject();
    await pickStub();
    await userEvent.click(
      screen.getByRole("radio", { name: /selected targets only/i }),
    );
    const checkbox = await screen.findByRole("checkbox", { name: /t-1/i });
    await userEvent.click(checkbox);
    expect(checkbox).toBeChecked();
    await userEvent.click(checkbox);
    expect(checkbox).not.toBeChecked();
  });

  it("falls back to a generic start error when the start-leg failure isn't a detail kind", async () => {
    withDeps();
    server.use(
      msw.post("/api/scan-runs/", () =>
        HttpResponse.json(makeScanRun({ id: "r-queued" }), { status: 201 }),
      ),
      msw.post("/api/scan-runs/r-queued/start/", () =>
        HttpResponse.error(),
      ),
    );
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await pickProject();
    await pickStub();
    await userEvent.click(
      screen.getByRole("button", { name: "Create and start" }),
    );
    expect(
      await screen.findByText(/could not start the scan run/i),
    ).toBeInTheDocument();
  });

  it("shows the 'No active targets.' message inside the selected-checkbox list when empty", async () => {
    withDeps({ targets: [TARGET_RETIRED] });
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await pickProject();
    await pickStub();
    await userEvent.click(
      screen.getByRole("radio", { name: /selected targets only/i }),
    );
    expect(
      screen.getAllByText(/No active targets/i).length,
    ).toBeGreaterThanOrEqual(2);
  });

  it("switches back from 'selected only' to 'all active'", async () => {
    withDeps();
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await pickProject();
    await pickStub();
    await userEvent.click(
      screen.getByRole("radio", { name: /selected targets only/i }),
    );
    expect(screen.getByRole("checkbox", { name: /t-1/i })).toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("radio", { name: /all active project targets/i }),
    );
    expect(
      screen.queryByRole("checkbox", { name: /t-1/i }),
    ).not.toBeInTheDocument();
  });

  it("blocks submit when 'selected only' is on and no targets are checked", async () => {
    withDeps();
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await pickProject();
    await pickStub();
    await userEvent.click(
      screen.getByRole("radio", { name: /selected targets only/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    expect(
      await screen.findByText(/at least one target is required/i),
    ).toBeInTheDocument();
  });

  it("sends only the checked target_ids when 'selected only' is on", async () => {
    withDeps({ targets: [TARGET_ACTIVE, { ...TARGET_ACTIVE, id: "t-other" }] });
    let received: { target_ids?: string[] } = {};
    server.use(
      msw.post("/api/scan-runs/", async ({ request }) => {
        received = (await request.json()) as typeof received;
        return HttpResponse.json(makeScanRun(), { status: 201 });
      }),
    );
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await pickProject();
    await pickStub();
    await userEvent.click(
      screen.getByRole("radio", { name: /selected targets only/i }),
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: /t-other/i }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    await waitFor(() => expect(received.target_ids).toEqual(["t-other"]));
  });
});

describe("CreateScanRun — server errors flow through applyParsedError", () => {
  it("renders backend-unreachable on network failure of create", async () => {
    withDeps();
    server.use(msw.post("/api/scan-runs/", () => HttpResponse.error()));
    renderWithProviders(<CreateScanRun />, { route: "/scan-runs/new" });
    await pickProject();
    await pickStub();
    await userEvent.click(
      screen.getByRole("button", { name: "Create scan run" }),
    );
    expect(
      await screen.findByText(/backend unreachable/i),
    ).toBeInTheDocument();
  });

  it("Cancel button navigates back to /scan-runs", async () => {
    withDeps();
    renderWithProviders(
      <>
        <CreateScanRun />
        <LocationProbe />
      </>,
      { route: "/scan-runs/new" },
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/scan-runs"),
    );
  });
});
