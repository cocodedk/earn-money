import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { AddTarget } from "./AddTarget";

beforeEach(() => window.localStorage.clear());

function LocationProbe() {
  return <span data-testid="loc">{useLocation().pathname}</span>;
}

function withProject() {
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
            target_count: 0,
            scan_run_count: 0,
            created_at: "2026-05-18T20:00:00.000000Z",
          },
        ],
      }),
    ),
  );
}

describe("AddTarget", () => {
  it("blocks when no current project is set", () => {
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    expect(screen.getByText(/select a project/i)).toBeInTheDocument();
  });

  it("validates base_url is required", async () => {
    withProject();
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await screen.findByLabelText(/Base URL/);
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    expect(await screen.findByText(/required/i)).toBeInTheDocument();
  });

  it("validates base_url must start with http:// or https://", async () => {
    withProject();
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "dvwa.cocode.dk",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    expect(await screen.findByText(/must start with http/i)).toBeInTheDocument();
  });

  it("submits and routes back to /targets on success", async () => {
    withProject();
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json(
          {
            id: "t-new",
            project: "p1",
            base_url: "https://dvwa.cocode.dk",
            host: null,
            ip: null,
            status: "active",
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        ),
      ),
    );
    renderWithProviders(
      <>
        <AddTarget />
        <LocationProbe />
      </>,
      { route: "/targets/new" },
    );
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/targets"),
    );
  });

  it("renders non_field_errors above the form", async () => {
    withProject();
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json(
          { non_field_errors: ["target with this project and base url already exists."] },
          { status: 400 },
        ),
      ),
    );
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    expect(await screen.findByText(/already exists/i)).toBeInTheDocument();
  });

  it("renders field-keyed errors under matching input", async () => {
    withProject();
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json(
          { host: ["invalid host"] },
          { status: 400 },
        ),
      ),
    );
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    expect(await screen.findByText("invalid host")).toBeInTheDocument();
  });

  it("renders generic message on 5xx", async () => {
    withProject();
    server.use(
      msw.post("/api/targets/", () => HttpResponse.json({}, { status: 503 })),
    );
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    expect(
      await screen.findByText(/something went wrong/i),
    ).toBeInTheDocument();
  });

  it("renders detail message on non-validation 4xx", async () => {
    withProject();
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json({ detail: "Forbidden." }, { status: 403 }),
      ),
    );
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    expect(await screen.findByText("Forbidden.")).toBeInTheDocument();
  });

  it("renders backend unreachable on network failure", async () => {
    withProject();
    server.use(msw.post("/api/targets/", () => HttpResponse.error()));
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
  });

  it("omits host and ip from the body when both inputs are blank", async () => {
    withProject();
    let received: Record<string, unknown> | null = null;
    server.use(
      msw.post("/api/targets/", async ({ request }) => {
        received = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: "t-new",
            project: "p1",
            base_url: "https://dvwa.cocode.dk",
            host: null,
            ip: null,
            status: "active",
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    await waitFor(() => expect(received).not.toBeNull());
    expect(received).toEqual({
      project: "p1",
      base_url: "https://dvwa.cocode.dk",
    });
    expect("host" in received!).toBe(false);
    expect("ip" in received!).toBe(false);
  });

  it("includes only host when host is filled but ip is blank", async () => {
    withProject();
    let received: Record<string, unknown> | null = null;
    server.use(
      msw.post("/api/targets/", async ({ request }) => {
        received = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: "t-new",
            project: "p1",
            base_url: "https://dvwa.cocode.dk",
            host: "dvwa.cocode.dk",
            ip: null,
            status: "active",
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.type(screen.getByLabelText(/Host/), "dvwa.cocode.dk");
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    await waitFor(() => expect(received).not.toBeNull());
    expect(received!.host).toBe("dvwa.cocode.dk");
    expect("ip" in received!).toBe(false);
  });

  it("treats whitespace-only host as blank (omitted from the body)", async () => {
    withProject();
    let received: Record<string, unknown> | null = null;
    server.use(
      msw.post("/api/targets/", async ({ request }) => {
        received = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: "t-new",
            project: "p1",
            base_url: "https://dvwa.cocode.dk",
            host: null,
            ip: null,
            status: "active",
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.type(screen.getByLabelText(/Host/), "   ");
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    await waitFor(() => expect(received).not.toBeNull());
    expect("host" in received!).toBe(false);
  });

  it("accepts typing into the Host and IP fields", async () => {
    withProject();
    let received: { host: string | null; ip: string | null } = {
      host: null,
      ip: null,
    };
    server.use(
      msw.post("/api/targets/", async ({ request }) => {
        const body = (await request.json()) as { host: string | null; ip: string | null };
        received = body;
        return HttpResponse.json(
          {
            id: "t-new",
            project: "p1",
            base_url: "https://x",
            host: body.host,
            ip: body.ip,
            status: "active",
            created_at: "2026-05-18T20:00:00.000000Z",
          },
          { status: 201 },
        );
      }),
    );
    renderWithProviders(<AddTarget />, { route: "/targets/new" });
    await userEvent.type(
      await screen.findByLabelText(/Base URL/),
      "https://dvwa.cocode.dk",
    );
    await userEvent.type(screen.getByLabelText(/Host/), "dvwa.cocode.dk");
    await userEvent.type(screen.getByLabelText(/^IP/), "127.0.0.1");
    await userEvent.click(screen.getByRole("button", { name: "Add target" }));
    await waitFor(() => expect(received.host).toBe("dvwa.cocode.dk"));
    expect(received.ip).toBe("127.0.0.1");
  });
});
