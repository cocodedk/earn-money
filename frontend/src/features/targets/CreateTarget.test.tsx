import { describe, it, expect } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { LocationProbe, withPaginated } from "../../test/helpers";
import { CreateTarget } from "./CreateTarget";

const PROJECT = {
  id: "p-1",
  name: "Local Lab",
  description: "",
  target_count: 0,
  scan_run_count: 0,
  created_at: "2026-05-19T08:00:00.000000Z",
};

const withProjects = (rows: unknown[]) =>
  withPaginated("/api/projects/", rows);

function trackPostCount() {
  let count = 0;
  server.use(
    msw.post("/api/targets/", () => {
      count += 1;
      return HttpResponse.json({}, { status: 201 });
    }),
  );
  return () => count;
}

async function pickProject(name = "Local Lab") {
  const select = await screen.findByLabelText(/Project/);
  await waitFor(() => expect(select).not.toBeDisabled());
  await userEvent.selectOptions(select, name);
}

async function typeBaseUrl(value: string) {
  await userEvent.type(screen.getByLabelText(/Base URL/), value);
}

describe("CreateTarget — happy paths", () => {
  it("submits and routes back to /targets on success (all fields)", async () => {
    withProjects([PROJECT]);
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json(
          {
            id: "t-new",
            project: "p-1",
            base_url: "https://dvwa.cocode.dk",
            host: "dvwa.cocode.dk",
            ip: "127.0.0.1",
            status: "active",
            created_at: "2026-05-19T08:00:00.000000Z",
            updated_at: "2026-05-19T08:00:00.000000Z",
          },
          { status: 201 },
        ),
      ),
    );
    renderWithProviders(
      <>
        <CreateTarget />
        <LocationProbe />
      </>,
      { route: "/targets/new" },
    );
    await pickProject();
    await typeBaseUrl("https://dvwa.cocode.dk");
    await userEvent.type(screen.getByLabelText(/^Host/), "dvwa.cocode.dk");
    await userEvent.type(screen.getByLabelText(/^IP/), "127.0.0.1");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    await waitFor(() =>
      expect(screen.getByTestId("loc").textContent).toBe("/targets"),
    );
  });

  it("omits blank host and ip from the request body", async () => {
    withProjects([PROJECT]);
    let received: { host?: string; ip?: string | null } = {};
    server.use(
      msw.post("/api/targets/", async ({ request }) => {
        received = (await request.json()) as typeof received;
        return HttpResponse.json({}, { status: 201 });
      }),
    );
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https://dvwa.cocode.dk");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    await waitFor(() => expect(received).not.toEqual({}));
    expect(received.host).toBeUndefined();
    expect(received.ip).toBeUndefined();
  });
});

describe("CreateTarget — projects-query branches", () => {
  it("disables project select while projects are loading", async () => {
    // Never-resolving handler keeps the projects query in its loading
    // state for the lifetime of this test — no timer to drain.
    server.use(msw.get("/api/projects/", () => new Promise(() => {})));
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    const select = await screen.findByLabelText(/Project/);
    expect(select).toBeDisabled();
    expect(screen.getByText(/Loading projects/i)).toBeInTheDocument();
  });

  it("shows an error callout when the projects query fails", async () => {
    server.use(msw.get("/api/projects/", () => HttpResponse.error()));
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    expect(
      await screen.findByText(/could not load projects/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Project/)).toBeDisabled();
  });

  it("links to /projects/new when the projects list is empty", async () => {
    withProjects([]);
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    const link = await screen.findByRole("link", {
      name: /create a project first/i,
    });
    expect(link).toHaveAttribute("href", "/projects/new");
    expect(screen.getByLabelText(/Project/)).toBeDisabled();
  });
});

describe("CreateTarget — base_url validation (no network call)", () => {
  it("rejects empty base_url", async () => {
    withProjects([PROJECT]);
    const calls = trackPostCount();
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(
      await screen.findByText(/base_url is required/i),
    ).toBeInTheDocument();
    expect(calls()).toBe(0);
  });

  it("rejects base_url without scheme", async () => {
    withProjects([PROJECT]);
    const calls = trackPostCount();
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("not-a-url");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(
      await screen.findByText(/must start with http:\/\/ or https:\/\//i),
    ).toBeInTheDocument();
    expect(calls()).toBe(0);
  });

  it('rejects "https://" with empty authority', async () => {
    withProjects([PROJECT]);
    const calls = trackPostCount();
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https://");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(
      await screen.findByText(/must start with http:\/\/ or https:\/\//i),
    ).toBeInTheDocument();
    expect(calls()).toBe(0);
  });

  it("rejects an unclosed IPv6 bracket (WHATWG URL parse rejects)", async () => {
    withProjects([PROJECT]);
    const calls = trackPostCount();
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    // `[` is a userEvent.type keyboard descriptor — set the value via
    // fireEvent.change instead so the literal string reaches the input.
    fireEvent.change(screen.getByLabelText(/Base URL/), {
      target: { value: "https://[broken" },
    });
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(
      await screen.findByText(/Enter a valid URL/i),
    ).toBeInTheDocument();
    expect(calls()).toBe(0);
  });

  it('rejects "https:///path" with empty authority', async () => {
    withProjects([PROJECT]);
    const calls = trackPostCount();
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https:///path");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(
      await screen.findByText(/must start with http:\/\/ or https:\/\//i),
    ).toBeInTheDocument();
    expect(calls()).toBe(0);
  });
});

describe("CreateTarget — server errors", () => {
  it("renders a server field error on the project field", async () => {
    withProjects([PROJECT]);
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json(
          { project: ["Invalid project."] },
          { status: 400 },
        ),
      ),
    );
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https://dvwa.cocode.dk");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(await screen.findByText("Invalid project.")).toBeInTheDocument();
  });

  it("renders a backend-unreachable banner on network failure", async () => {
    withProjects([PROJECT]);
    server.use(msw.post("/api/targets/", () => HttpResponse.error()));
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https://dvwa.cocode.dk");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(
      await screen.findByText(/backend unreachable/i),
    ).toBeInTheDocument();
  });

  it("renders a non_field_errors banner", async () => {
    withProjects([PROJECT]);
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json(
          { non_field_errors: ["Bad combo."] },
          { status: 400 },
        ),
      ),
    );
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https://dvwa.cocode.dk");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(await screen.findByText("Bad combo.")).toBeInTheDocument();
  });

  it("renders a detail message on a non-400 4xx", async () => {
    withProjects([PROJECT]);
    server.use(
      msw.post("/api/targets/", () =>
        HttpResponse.json({ detail: "Forbidden." }, { status: 403 }),
      ),
    );
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https://dvwa.cocode.dk");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(await screen.findByText("Forbidden.")).toBeInTheDocument();
  });

  it("renders a generic message on 5xx", async () => {
    withProjects([PROJECT]);
    server.use(
      msw.post("/api/targets/", () => HttpResponse.json({}, { status: 503 })),
    );
    renderWithProviders(<CreateTarget />, { route: "/targets/new" });
    await pickProject();
    await typeBaseUrl("https://dvwa.cocode.dk");
    await userEvent.click(screen.getByRole("button", { name: "Create target" }));
    expect(
      await screen.findByText(/something went wrong/i),
    ).toBeInTheDocument();
  });
});
