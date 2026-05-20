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

describe("TargetResult — errors + edge cases", () => {
  it("renders error callouts when each child endpoint errors", async () => {
    server.use(
      msw.get(`/api/targets/${TARGET_ID}/`, () => HttpResponse.json(TARGET)),
      msw.get("/api/scan-runs/", () => HttpResponse.error()),
      msw.get("/api/findings/", () => HttpResponse.error()),
      msw.get("/api/evidence/", () => HttpResponse.error()),
      msw.get("/api/events/", () => HttpResponse.error()),
    );
    mountTargetResult();
    await screen.findByText(/Could not load scan runs/);
    expect(screen.getByText(/Could not load findings/)).toBeInTheDocument();
    expect(screen.getByText(/Could not load evidence/)).toBeInTheDocument();
    expect(screen.getByText(/Could not load events/)).toBeInTheDocument();
  });

  it("renders dashes for null ip / non-null timestamps / blank confidence / null evidence fields", async () => {
    server.use(
      msw.get(`/api/targets/${TARGET_ID}/`, () =>
        HttpResponse.json({ ...TARGET, ip: null }),
      ),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json(
          paginatedJson([
            makeScanRun({
              id: "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
              started_at: "2026-05-20T08:00:00Z",
              finished_at: "2026-05-20T09:00:00Z",
            }),
          ]),
        ),
      ),
      msw.get("/api/findings/", () =>
        HttpResponse.json(
          paginatedJson([
            makeFinding({
              id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
              confidence: "" as unknown as "low",
            }),
          ]),
        ),
      ),
      msw.get("/api/evidence/", () =>
        HttpResponse.json(
          paginatedJson([
            makeEvidence({
              id: "eeeeeeee-bbbb-bbbb-bbbb-bbbbbbbbbbb1",
              url: null,
              method: null,
              field: null,
              matched_value: null,
            }),
          ]),
        ),
      ),
      msw.get("/api/events/", () => HttpResponse.json(emptyPage())),
    );
    mountTargetResult();
    await screen.findByTestId(
      "target-scan-run-row-11111111-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
    );
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("shows truncation hints when next != null on each section", async () => {
    server.use(
      msw.get(`/api/targets/${TARGET_ID}/`, () => HttpResponse.json(TARGET)),
      msw.get("/api/scan-runs/", () =>
        HttpResponse.json(
          paginatedJson(
            [makeScanRun({ id: "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaa1" })],
            "/api/scan-runs/?page=2",
          ),
        ),
      ),
      msw.get("/api/findings/", () =>
        HttpResponse.json(
          paginatedJson(
            [makeFinding({ id: "ffffffff-aaaa-aaaa-aaaa-aaaaaaaaaaa1" })],
            "/api/findings/?page=2",
          ),
        ),
      ),
      msw.get("/api/evidence/", () =>
        HttpResponse.json(
          paginatedJson(
            [makeEvidence({ id: "eeeeeeee-bbbb-bbbb-bbbb-bbbbbbbbbbb1" })],
            "/api/evidence/?page=2",
          ),
        ),
      ),
      msw.get("/api/events/", () =>
        HttpResponse.json(
          paginatedJson(
            [makeEvent({ id: "dddddddd-cccc-cccc-cccc-cccccccccc01" })],
            "/api/events/?page=2",
          ),
        ),
      ),
    );
    mountTargetResult();
    expect(
      await screen.findByTestId("target-scan-runs-truncation"),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("target-findings-truncation"),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("target-evidence-truncation"),
    ).toBeInTheDocument();
    expect(
      await screen.findByTestId("target-events-truncation"),
    ).toBeInTheDocument();
  });
});
