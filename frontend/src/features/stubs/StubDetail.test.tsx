import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { Route, Routes } from "react-router-dom";
import { StubDetail } from "./StubDetail";

function mountAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/stubs/:slug" element={<StubDetail />} />
    </Routes>,
    { route },
  );
}

describe("StubDetail", () => {
  it("renders the stub detail fields and the body", async () => {
    server.use(
      msw.get("/api/stubs/1.1/", () =>
        HttpResponse.json({
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
          body: "# Framework detection\n\nDetect the running framework.",
        }),
      ),
    );
    mountAt("/stubs/1.1");
    expect(await screen.findByText("Framework detection")).toBeInTheDocument();
    expect(screen.getByText("information-gathering")).toBeInTheDocument();
    expect(screen.getByText(/Detect the running framework/)).toBeInTheDocument();
  });

  it("falls back to dash for null fixture", async () => {
    server.use(
      msw.get("/api/stubs/1.2/", () =>
        HttpResponse.json({
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
          body: "# Server headers",
        }),
      ),
    );
    mountAt("/stubs/1.2");
    await screen.findByText("Server headers");
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders a callout when the stub is not found", async () => {
    server.use(
      msw.get("/api/stubs/9.9/", () =>
        HttpResponse.json({ detail: "Not found." }, { status: 404 }),
      ),
    );
    mountAt("/stubs/9.9");
    expect(await screen.findByText(/not found/i)).toBeInTheDocument();
  });
});
