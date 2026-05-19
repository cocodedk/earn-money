import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { StubDetail } from "./StubDetail";
import { makeStubWithBody } from "./__fixtures__/stub";

function renderAt(path: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/stubs/:slug" element={<StubDetail />} />
    </Routes>,
    { route: path },
  );
}

const FULL = makeStubWithBody();

describe("StubDetail", () => {
  it("renders the title, metadata, and the markdown body", async () => {
    server.use(msw.get("/api/stubs/1.1/", () => HttpResponse.json(FULL)));
    renderAt("/stubs/1.1");
    expect(
      await screen.findByText(/1\.1 · Framework detection/),
    ).toBeInTheDocument();
    expect(screen.getByText("Information gathering")).toBeInTheDocument();
    expect(screen.getByText("Content discovery")).toBeInTheDocument();
    expect(screen.getByTestId("status-done")).toBeInTheDocument();
    expect(
      screen.getByText(/Detect the application framework/),
    ).toBeInTheDocument();
  });

  it("renders an em-dash when spec_slug or category is empty", async () => {
    server.use(
      msw.get("/api/stubs/1.1/", () =>
        HttpResponse.json({ ...FULL, spec_slug: "", category: "" }),
      ),
    );
    renderAt("/stubs/1.1");
    const dashes = await screen.findAllByText("—");
    // category + spec_slug both render the dash.
    expect(dashes.length).toBeGreaterThanOrEqual(2);
  });

  it("renders Stub not found on 404 with a back link", async () => {
    server.use(
      msw.get("/api/stubs/9.9/", () =>
        HttpResponse.json({ detail: "No stub" }, { status: 404 }),
      ),
    );
    renderAt("/stubs/9.9");
    expect(await screen.findByText(/stub not found/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /back to stubs/i }),
    ).toHaveAttribute("href", "/stubs");
  });

  it("renders a Backend-unreachable callout on transport error", async () => {
    server.use(msw.get("/api/stubs/1.1/", () => HttpResponse.error()));
    renderAt("/stubs/1.1");
    expect(
      await screen.findByText(/backend unreachable/i),
    ).toBeInTheDocument();
  });

  it("shows a loading header before data resolves", async () => {
    server.use(msw.get("/api/stubs/1.1/", () => new Promise(() => {})));
    renderAt("/stubs/1.1");
    expect(await screen.findByText("Loading…")).toBeInTheDocument();
  });
});
