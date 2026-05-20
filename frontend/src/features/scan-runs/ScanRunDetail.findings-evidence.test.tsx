import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";
import { Routes, Route } from "react-router-dom";
import { http as msw, HttpResponse } from "msw";
import { server } from "../../test/server";
import { renderWithProviders } from "../../test/renderWithProviders";
import { withBareArray, withPaginated } from "../../test/helpers";
import { ScanRunDetail } from "./ScanRunDetail";
import { makeScanRun } from "./__fixtures__/scan-run";
import { makeStub } from "../stubs/__fixtures__/stub";

const ID = "11111111-1111-1111-1111-111111111111";

function mountAt(id: string) {
  withPaginated("/api/projects/", []);
  withBareArray("/api/stubs/", [makeStub()]);
  return renderWithProviders(
    <Routes>
      <Route path="/scan-runs/:id" element={<ScanRunDetail />} />
    </Routes>,
    { route: `/scan-runs/${id}` },
  );
}

describe("ScanRunDetail findings + evidence panels", () => {
  it("renders Findings panel below targets table", async () => {
    server.use(
      msw.get(`/api/scan-runs/${ID}/`, () =>
        HttpResponse.json(makeScanRun({ id: ID, status: "done" })),
      ),
    );
    mountAt(ID);
    expect(await screen.findByText(/Findings \(0\)/)).toBeInTheDocument();
  });
});
