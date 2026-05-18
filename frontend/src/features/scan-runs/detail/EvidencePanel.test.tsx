import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EvidencePanel } from "./EvidencePanel";

describe("EvidencePanel", () => {
  it("renders evidence rows with all fields", () => {
    render(
      <EvidencePanel
        rows={[
          {
            id: "e1",
            scan_run: "r1",
            target: "t1abcdef",
            finding: "f1",
            source: "header.X-Powered-By",
            url: "https://dvwa.cocode.dk/",
            method: "GET",
            field: "X-Powered-By",
            matched_value: "PHP/7.4",
            raw_excerpt: null,
            content_hash: "ab12",
            data: {},
            created_at: "2026-05-18T20:00:00.000000Z",
          },
        ]}
      />,
    );
    expect(screen.getByText("header.X-Powered-By")).toBeInTheDocument();
    expect(screen.getByText("PHP/7.4")).toBeInTheDocument();
  });

  it("falls back to dashes when nullable fields are empty", () => {
    render(
      <EvidencePanel
        rows={[
          {
            id: "e1",
            scan_run: "r1",
            target: "t1",
            finding: null,
            source: "x",
            url: null,
            method: null,
            field: null,
            matched_value: null,
            raw_excerpt: null,
            content_hash: "ab12",
            data: {},
            created_at: "2026-05-18T20:00:00.000000Z",
          },
        ]}
      />,
    );
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(4);
  });

  it("renders empty state", () => {
    render(<EvidencePanel rows={[]} />);
    expect(screen.getByText(/no evidence yet/i)).toBeInTheDocument();
  });

  it("renders loading skeleton", () => {
    render(<EvidencePanel rows={[]} isLoading />);
    expect(screen.getAllByTestId("skeleton-row").length).toBeGreaterThan(0);
  });
});
