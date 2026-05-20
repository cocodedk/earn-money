import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "./test/server";
import { renderWithProviders } from "./test/renderWithProviders";
import {
  makeStub,
  makeStubWithBody,
} from "./features/stubs/__fixtures__/stub";
import App from "./App";

beforeEach(() => window.localStorage.clear());

describe("end-to-end · stubs", () => {
  it("walks the stubs list → detail → back flow", async () => {
    const stub = makeStub();
    server.use(
      msw.get("/api/stubs/", () => HttpResponse.json([stub])),
      msw.get("/api/stubs/1.1/", () => HttpResponse.json(makeStubWithBody())),
    );

    renderWithProviders(<App />, { route: "/stubs" });

    expect(await screen.findByText("Framework detection")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "1.1" }));
    await waitFor(() =>
      expect(
        screen.getByText(/Detect the application framework/),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/1\.1 · Framework detection/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "Stubs" }));
    await waitFor(() =>
      expect(screen.getByText("Framework detection")).toBeInTheDocument(),
    );
  });
});
