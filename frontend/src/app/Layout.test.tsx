import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./Layout";

function setup(initialRoute = "/projects") {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/projects" element={<div>projects body</div>} />
          <Route path="/targets" element={<div>targets body</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
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
    // data-active lives on the inner span because NavLink's `isActive` is exposed there.
    expect(screen.getByText("Targets")).toHaveAttribute("data-active", "true");
  });
});
