import { describe, it, expect } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { CreateProject } from "./CreateProject";

function LocationProbe() {
  return <span data-testid="loc">{useLocation().pathname}</span>;
}

describe("CreateProject", () => {
  it("validates required name field locally", async () => {
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("name is required")).toBeInTheDocument();
  });

  it("submits and routes back to /projects on success", async () => {
    server.use(
      msw.post("/api/projects/", () =>
        HttpResponse.json(
          {
            id: "u-new",
            name: "X",
            description: "Y",
            target_count: 0,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        ),
      ),
    );
    renderWithProviders(
      <>
        <CreateProject />
        <LocationProbe />
      </>,
      { route: "/projects/new" },
    );
    await userEvent.type(screen.getByLabelText(/Name/), "X");
    await userEvent.type(screen.getByLabelText(/Description/), "Y");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/projects"),
    );
  });

  it("submits the body shape {name, description} matching the contract", async () => {
    let received: Record<string, unknown> | null = null;
    server.use(
      msw.post("/api/projects/", async ({ request }) => {
        received = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: "u-new",
            name: "Acme",
            description: "Lab",
            target_count: 0,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.type(screen.getByLabelText(/Name/), "Acme");
    await userEvent.type(screen.getByLabelText(/Description/), "Lab");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() => expect(received).not.toBeNull());
    expect(received).toEqual({ name: "Acme", description: "Lab" });
  });

  it("sends description as empty string (not null) when left blank", async () => {
    let received: Record<string, unknown> | null = null;
    server.use(
      msw.post("/api/projects/", async ({ request }) => {
        received = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: "u-new",
            name: "Acme",
            description: "",
            target_count: 0,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.type(screen.getByLabelText(/Name/), "Acme");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    await waitFor(() => expect(received).not.toBeNull());
    expect(received!.description).toBe("");
    expect(received!.description).not.toBeNull();
  });

  it("renders server field errors under the matching input", async () => {
    server.use(
      msw.post("/api/projects/", () =>
        HttpResponse.json({ name: ["already exists"] }, { status: 400 }),
      ),
    );
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.type(screen.getByLabelText(/Name/), "X");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("already exists")).toBeInTheDocument();
  });

  it("renders non_field_errors above the form", async () => {
    server.use(
      msw.post("/api/projects/", () =>
        HttpResponse.json({ non_field_errors: ["bad combo"] }, { status: 400 }),
      ),
    );
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.type(screen.getByLabelText(/Name/), "X");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("bad combo")).toBeInTheDocument();
  });

  it("renders a generic message on 5xx", async () => {
    server.use(
      msw.post("/api/projects/", () => HttpResponse.json({}, { status: 503 })),
    );
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.type(screen.getByLabelText(/Name/), "X");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(
      await screen.findByText(/something went wrong/i),
    ).toBeInTheDocument();
  });

  it("renders backend unreachable on network failure", async () => {
    server.use(msw.post("/api/projects/", () => HttpResponse.error()));
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.type(screen.getByLabelText(/Name/), "X");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
  });

  it("renders detail message on non-validation 4xx", async () => {
    server.use(
      msw.post("/api/projects/", () =>
        HttpResponse.json({ detail: "Forbidden." }, { status: 403 }),
      ),
    );
    renderWithProviders(<CreateProject />, { route: "/projects/new" });
    await userEvent.type(screen.getByLabelText(/Name/), "X");
    await userEvent.click(screen.getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("Forbidden.")).toBeInTheDocument();
  });
});
