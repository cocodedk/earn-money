import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { makeScanRun } from "../scan-runs/__fixtures__/scan-run";
import { makeFinding } from "../scan-runs/__fixtures__/finding";
import { makeEvidence } from "../scan-runs/__fixtures__/evidence";
import { makeEvent } from "../scan-runs/__fixtures__/event";
import {
  TARGET,
  TARGET_ID,
  mountTargetResult,
  paginatedJson,
  emptyPage,
} from "./TargetResult/__fixtures__/testkit";

describe("TargetResult — happy path + empty states", () => {
  it("renders header, meta, and all 4 child sections with row counts", async () => {
    server.use(
      msw.get(`/api/targets/${TARGET_ID}/`, () => HttpResponse.json(TARGET)),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json(
          paginatedJson([
            makeScanRun({
              id: "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
              status: "running",
            }),
            makeScanRun({
              id: "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaa2",
              status: "done",
            }),
          ]),
        ),
      ),
      msw.get("/api/findings/", () =>
        HttpResponse.json(
          paginatedJson([
            makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaa1" }),
            makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaa2" }),
            makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaa3" }),
          ]),
        ),
      ),
      msw.get("/api/evidence/", () =>
        HttpResponse.json(
          paginatedJson(
            Array.from({ length: 5 }, (_, i) =>
              makeEvidence({
                id: `eeeeeeee-bbbb-bbbb-bbbb-bbbbbbbbbbb${i + 1}`,
              }),
            ),
          ),
        ),
      ),
      msw.get("/api/events/", () =>
        HttpResponse.json(
          paginatedJson(
            Array.from({ length: 4 }, (_, i) =>
              makeEvent({
                id: `dddddddd-cccc-cccc-cccc-cccccccccc0${i + 1}`,
              }),
            ),
          ),
        ),
      ),
    );
    mountTargetResult();
    expect(
      await screen.findByText(/Target · 22222222 · https:\/\/dvwa\.cocode\.dk/),
    ).toBeInTheDocument();
    expect(await screen.findByText("Local Lab")).toBeInTheDocument();
    expect(screen.getByText("1.2.3.4")).toBeInTheDocument();
    expect(await screen.findByTestId("target-scan-runs-section")).toBeInTheDocument();
    expect(await screen.findByTestId("target-findings-section")).toBeInTheDocument();
    expect(await screen.findByTestId("target-evidence-section")).toBeInTheDocument();
    expect(await screen.findByTestId("target-events-section")).toBeInTheDocument();
    expect(await screen.findAllByTestId(/^target-scan-run-row-/)).toHaveLength(2);
    expect(await screen.findAllByTestId(/^target-finding-row-/)).toHaveLength(3);
    expect(await screen.findAllByTestId(/^target-evidence-row-/)).toHaveLength(5);
    expect(await screen.findAllByTestId(/^target-event-row-/)).toHaveLength(4);
  });

  it("renders empty states for each section when counts are zero", async () => {
    server.use(
      msw.get(`/api/targets/${TARGET_ID}/`, () => HttpResponse.json(TARGET)),
      msw.get("/api/scan-runs/", () => HttpResponse.json(emptyPage())),
      msw.get("/api/findings/", () => HttpResponse.json(emptyPage())),
      msw.get("/api/evidence/", () => HttpResponse.json(emptyPage())),
      msw.get("/api/events/", () => HttpResponse.json(emptyPage())),
    );
    mountTargetResult();
    expect(await screen.findByTestId("target-scan-runs-empty")).toBeInTheDocument();
    expect(await screen.findByTestId("target-findings-empty")).toBeInTheDocument();
    expect(await screen.findByTestId("target-evidence-empty")).toBeInTheDocument();
    expect(await screen.findByTestId("target-events-empty")).toBeInTheDocument();
  });

  it("renders TargetAuthEventsPanel between Evidence and Events when there are auth events", async () => {
    const authEventsPage = (rows: ReturnType<typeof makeEvent>[]) => ({
      count: rows.length,
      next: null,
      previous: null,
      results: rows,
    });

    server.use(
      msw.get(`/api/targets/${TARGET_ID}/`, () => HttpResponse.json(TARGET)),
      msw.get("/api/scan-runs/", () => HttpResponse.json(emptyPage())),
      msw.get("/api/findings/", () => HttpResponse.json(emptyPage())),
      msw.get("/api/evidence/", () => HttpResponse.json(emptyPage())),
      msw.get("/api/events/", ({ request }) => {
        const types = new URL(request.url).searchParams.getAll("type");
        if (types.includes("auth.probe_refused")) {
          return HttpResponse.json(
            authEventsPage([
              makeEvent({
                id: "auth-1",
                type: "auth.fixture_required",
                message: "fixture missing",
              }),
            ]),
          );
        }
        return HttpResponse.json(emptyPage());
      }),
    );
    mountTargetResult();
    const evidence = await screen.findByTestId("target-evidence-section");
    const auth = await screen.findByTestId("target-auth-events-section");
    const events = await screen.findByTestId("target-events-section");
    expect(evidence.parentElement).toBe(auth.parentElement);
    expect(auth.parentElement).toBe(events.parentElement);
    const siblings = Array.from(auth.parentElement!.children);
    expect(siblings.indexOf(evidence)).toBeLessThan(siblings.indexOf(auth));
    expect(siblings.indexOf(auth)).toBeLessThan(siblings.indexOf(events));
  });
});
