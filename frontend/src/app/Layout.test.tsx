import { describe, it, expect, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { renderWithProviders } from "../test/renderWithProviders";
import { Layout } from "./Layout";

beforeEach(() => window.localStorage.clear());

function setup(initialRoute = "/projects") {
  return renderWithProviders(
    <Routes>
      <Route element={<Layout />}>
        <Route path="/projects" element={<div>projects body</div>} />
        <Route path="/projects/new" element={<div>new project body</div>} />
        <Route path="/targets" element={<div>targets body</div>} />
      </Route>
    </Routes>,
    { route: initialRoute },
  );
}

describe("Layout", () => {
  it("renders the app name and all sidebar items", () => {
    setup();
    expect(screen.getByText("Cookbook scanner")).toBeInTheDocument();
    [
      "Projects",
      "Targets",
      "Stubs",
      "Scan Runs",
      "Findings",
      "Evidence",
      "Settings",
    ].forEach((label) => {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    });
  });

  it("renders the outlet contents", () => {
    setup();
    expect(screen.getByText("projects body")).toBeInTheDocument();
  });

  it("marks the active route", () => {
    setup("/targets");
    expect(screen.getByText("Targets")).toHaveAttribute("data-active", "true");
  });

  it("renders the connection pill and current-project chip in the top bar", async () => {
    setup();
    expect(
      await screen.findByTestId("connection-pill"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("current-project-chip")).toBeInTheDocument();
  });

  it("moves the active marker when navigating to a different route", async () => {
    setup("/projects");
    expect(screen.getByText("Projects")).toHaveAttribute("data-active", "true");
    await userEvent.click(screen.getByRole("link", { name: "Targets" }));
    await waitFor(() =>
      expect(screen.getByText("Targets")).toHaveAttribute("data-active", "true"),
    );
  });

  it("keeps the parent active on a child route", () => {
    setup("/projects/new");
    expect(screen.getByText("Projects")).toHaveAttribute("data-active", "true");
  });

  it("renders an icon for each of the seven nav items", () => {
    const { container } = setup();
    expect(container.querySelectorAll("nav svg")).toHaveLength(7);
  });

  it("exposes a stable testid on each nav link", () => {
    setup();
    [
      "nav-projects",
      "nav-targets",
      "nav-stubs",
      "nav-scan-runs",
      "nav-findings",
      "nav-evidence",
      "nav-settings",
    ].forEach((testid) => {
      expect(screen.getByTestId(testid)).toBeInTheDocument();
    });
  });
});
