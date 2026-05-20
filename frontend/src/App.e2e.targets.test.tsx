import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "./test/server";
import { renderWithProviders } from "./test/renderWithProviders";
import App from "./App";

beforeEach(() => window.localStorage.clear());

describe("end-to-end · targets", () => {
  it("creates a target after a project and lands on a populated targets list", async () => {
    let storedProject: { id: string; name: string } | null = null;
    let storedTarget: {
      id: string;
      project: string;
      base_url: string;
      host: string;
      ip: string | null;
    } | null = null;
    server.use(
      msw.get("/api/projects/", () =>
        HttpResponse.json({
          count: storedProject ? 1 : 0,
          next: null,
          previous: null,
          results: storedProject
            ? [
                {
                  id: storedProject.id,
                  name: storedProject.name,
                  description: "",
                  target_count: storedTarget ? 1 : 0,
                  scan_run_count: 0,
                  created_at: "2026-05-19T08:00:00.000000Z",
                },
              ]
            : [],
        }),
      ),
      msw.post("/api/projects/", async ({ request }) => {
        const body = (await request.json()) as { name: string };
        storedProject = { id: "p-1", name: body.name };
        return HttpResponse.json(
          {
            id: "p-1",
            name: body.name,
            description: "",
            target_count: 0,
            scan_run_count: 0,
            created_at: "2026-05-19T08:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
      msw.get("/api/targets/", () =>
        HttpResponse.json({
          count: storedTarget ? 1 : 0,
          next: null,
          previous: null,
          results: storedTarget
            ? [
                {
                  ...storedTarget,
                  status: "active",
                  created_at: "2026-05-19T08:00:00.000000Z",
                  updated_at: "2026-05-19T08:00:00.000000Z",
                },
              ]
            : [],
        }),
      ),
      msw.post("/api/targets/", async ({ request }) => {
        const body = (await request.json()) as {
          project: string;
          base_url: string;
        };
        storedTarget = {
          id: "t-1",
          project: body.project,
          base_url: body.base_url,
          host: "dvwa.cocode.dk",
          ip: null,
        };
        return HttpResponse.json(
          {
            ...storedTarget,
            status: "active",
            created_at: "2026-05-19T08:00:00.000000Z",
            updated_at: "2026-05-19T08:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );

    renderWithProviders(<App />, { route: "/projects" });

    await userEvent.click(await screen.findByTestId("page-header-create"));
    await userEvent.type(screen.getByLabelText(/Name/), "Local Lab");
    await userEvent.type(screen.getByLabelText(/Description/), "lab");
    await userEvent.click(
      screen.getByRole("button", { name: "Create project" }),
    );
    await waitFor(() =>
      expect(screen.getByText("Local Lab")).toBeInTheDocument(),
    );

    await userEvent.click(screen.getByRole("link", { name: "Targets" }));
    expect(await screen.findByText("No targets yet.")).toBeInTheDocument();

    await userEvent.click(screen.getByTestId("page-header-create"));
    await userEvent.selectOptions(
      await screen.findByLabelText(/Project/),
      "Local Lab",
    );
    await userEvent.type(
      screen.getByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Create target" }),
    );

    await waitFor(() =>
      expect(screen.getByText("https://dvwa.cocode.dk")).toBeInTheDocument(),
    );
    expect(screen.getByText("dvwa.cocode.dk")).toBeInTheDocument();
  });
});
