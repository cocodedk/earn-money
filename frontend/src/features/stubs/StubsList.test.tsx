import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { StubsList } from "./StubsList";

const fixtures = [
  {
    slug: "1.1",
    phase: 1,
    spec: 1,
    title: "Framework detection",
    status: "done",
    fixture: "juiceshop",
    category: "information-gathering",
    phase_title: "Information gathering",
    phase_slug: "01-information-gathering",
    spec_slug: "01-framework-detection",
    path: "x",
  },
  {
    slug: "1.2",
    phase: 1,
    spec: 2,
    title: "Server headers",
    status: "in_progress",
    fixture: null,
    category: "information-gathering",
    phase_title: "Information gathering",
    phase_slug: "01-information-gathering",
    spec_slug: "02-server-headers",
    path: "x",
  },
  {
    slug: "2.1",
    phase: 2,
    spec: 1,
    title: "TBD",
    status: "pending",
    fixture: null,
    category: "auth",
    phase_title: "Auth",
    phase_slug: "02-auth",
    spec_slug: "01-tbd",
    path: "x",
  },
];

describe("StubsList", () => {
  it("renders rows with phase/title/category columns and a status badge", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.json(fixtures)));
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText("Framework detection")).toBeInTheDocument();
    expect(screen.getByText("Server headers")).toBeInTheDocument();
    expect(screen.getAllByTestId("status-badge").length).toBeGreaterThanOrEqual(3);
  });

  it("links each row title to /stubs/<slug>", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.json(fixtures)));
    renderWithProviders(<StubsList />, { route: "/stubs" });
    const link = await screen.findByRole("link", { name: "Framework detection" });
    expect(link).toHaveAttribute("href", "/stubs/1.1");
  });

  it("renders fixture column with — when null", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.json(fixtures)));
    renderWithProviders(<StubsList />, { route: "/stubs" });
    await screen.findByText("Server headers");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("shows the empty state when no stubs", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.json([])));
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText(/no stubs/i)).toBeInTheDocument();
  });

  it("renders a callout with retry on fetch error", async () => {
    server.use(msw.get("/api/stubs/", () => HttpResponse.error()));
    renderWithProviders(<StubsList />, { route: "/stubs" });
    expect(await screen.findByText(/backend unreachable/i)).toBeInTheDocument();
  });

  it("re-fetches when Retry is clicked", async () => {
    let calls = 0;
    server.use(
      msw.get("/api/stubs/", () => {
        calls += 1;
        return HttpResponse.error();
      }),
    );
    renderWithProviders(<StubsList />, { route: "/stubs" });
    await screen.findByText(/backend unreachable/i);
    const first = calls;
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByText(/backend unreachable/i);
    expect(calls).toBeGreaterThan(first);
  });
});
