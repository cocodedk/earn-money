import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { MissionsList } from "./MissionsList";
import { makeSession } from "./__fixtures__/mission";

function paged<T>(results: T[]) {
  return { count: results.length, next: null, previous: null, results };
}

describe("MissionsList", () => {
  it("renders sessions in a table with View links", async () => {
    server.use(
      msw.get("/api/agent/sessions/", () =>
        HttpResponse.json(paged([
          makeSession({ id: "s-1", mission_profile: "juice_shop", target_host: "juice.test" }),
          makeSession({ id: "s-2", mission_profile: "dvwa_scan", target_host: "dvwa.test", status: "failed" }),
        ])),
      ),
    );
    renderWithProviders(<MissionsList />);
    expect(await screen.findByText("juice_shop")).toBeInTheDocument();
    expect(screen.getByText("dvwa_scan")).toBeInTheDocument();
    expect(screen.getByText("juice.test")).toBeInTheDocument();
    expect(screen.getAllByText("View")).toHaveLength(2);
  });

  it("shows empty state when no sessions", async () => {
    server.use(
      msw.get("/api/agent/sessions/", () => HttpResponse.json(paged([]))),
    );
    renderWithProviders(<MissionsList />);
    expect(await screen.findByText("No missions yet.")).toBeInTheDocument();
  });
});
