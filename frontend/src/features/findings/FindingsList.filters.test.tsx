import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { FindingsList } from "./FindingsList";
import { paged, setupFiltersRefData } from "./__fixtures__/refData";

describe("FindingsList — URL <-> filters", () => {
  it("reads severity from URL ?severity=high and sends it on", async () => {
    setupFiltersRefData();
    let search = "";
    server.use(
      msw.get("/api/findings/", ({ request }) => {
        search = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    renderWithProviders(<FindingsList />, {
      route: "/findings?severity=high",
    });
    await waitFor(() => expect(search).toContain("severity=high"));
    const sev = (await screen.findByLabelText("Severity")) as HTMLSelectElement;
    expect(sev.value).toBe("high");
  });

  it("updates the select value when the user picks a severity", async () => {
    setupFiltersRefData();
    server.use(
      msw.get("/api/findings/", () => HttpResponse.json(paged([]))),
    );
    renderWithProviders(<FindingsList />, { route: "/findings" });
    const sev = (await screen.findByLabelText("Severity")) as HTMLSelectElement;
    await userEvent.selectOptions(sev, "medium");
    expect(sev.value).toBe("medium");
  });

  it("clearing a filter (selecting 'All …') removes it from the request URL", async () => {
    setupFiltersRefData();
    let lastSearch = "";
    server.use(
      msw.get("/api/findings/", ({ request }) => {
        lastSearch = new URL(request.url).search;
        return HttpResponse.json(paged([]));
      }),
    );
    renderWithProviders(<FindingsList />, {
      route: "/findings?severity=high",
    });
    const sev = (await screen.findByLabelText("Severity")) as HTMLSelectElement;
    await waitFor(() => expect(sev.value).toBe("high"));
    await userEvent.selectOptions(sev, "");
    await waitFor(() => expect(lastSearch).not.toContain("severity="));
  });
});
