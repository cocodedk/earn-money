import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { EvidenceList } from "./EvidenceList";
import { paged, setupFiltersRefData } from "./__fixtures__/refData";

describe("EvidenceList — URL <-> filters", () => {
  it("reads project from URL ?project=p-1 and sends it on", async () => {
    setupFiltersRefData();
    let search = "";
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    renderWithProviders(<EvidenceList />, {
      route: "/evidence?project=p-1",
    });
    await waitFor(() => expect(search).toContain("project=p-1"));
    const proj = (await screen.findByLabelText("Project")) as HTMLSelectElement;
    expect(proj.value).toBe("p-1");
  });

  it("updates the select value when the user picks a target", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/evidence/", () => HttpResponse.json(paged([]))),
    );
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    const tgt = (await screen.findByLabelText("Target")) as HTMLSelectElement;
    await waitFor(() =>
      expect(tgt.querySelector('option[value="t-1"]')).not.toBeNull(),
    );
    await userEvent.selectOptions(tgt, "t-1");
    expect(tgt.value).toBe("t-1");
  });

  it("source text input sends ?source=http-headers", async () => {
    setupFiltersRefData();
    let lastSearch = "";
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        lastSearch = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    renderWithProviders(<EvidenceList />, { route: "/evidence" });
    const src = (await screen.findByLabelText("Source")) as HTMLInputElement;
    await userEvent.type(src, "http-headers");
    await waitFor(() =>
      expect(lastSearch).toContain("source=http-headers"),
    );
  });

  it("clearing the source field removes it from the URL", async () => {
    setupFiltersRefData();
    let lastSearch = "";
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        lastSearch = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    renderWithProviders(<EvidenceList />, {
      route: "/evidence?source=http-headers",
    });
    const src = (await screen.findByLabelText("Source")) as HTMLInputElement;
    await waitFor(() => expect(src.value).toBe("http-headers"));
    await userEvent.clear(src);
    await waitFor(() => expect(lastSearch).not.toContain("source="));
  });

  it("clearing a select filter (selecting 'All …') removes it from the URL", async () => {
    setupFiltersRefData();
    let lastSearch = "";
    server.use(
      msw.get("/api/evidence/", ({ request }) => {
        lastSearch = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    renderWithProviders(<EvidenceList />, {
      route: "/evidence?project=p-1",
    });
    const proj = (await screen.findByLabelText("Project")) as HTMLSelectElement;
    await waitFor(() => expect(proj.value).toBe("p-1"));
    await userEvent.selectOptions(proj, "");
    await waitFor(() => expect(lastSearch).not.toContain("project="));
  });
});
