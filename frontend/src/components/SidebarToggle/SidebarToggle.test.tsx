import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SidebarToggle } from "./SidebarToggle";
import { setCollapsed } from "../../app/sidebar";

beforeEach(() => {
  setCollapsed(false);
  localStorage.clear();
});

describe("SidebarToggle", () => {
  it("renders expanded by default with ChevronsLeft", () => {
    render(<SidebarToggle />);
    const btn = screen.getByTestId("sidebar-toggle");
    expect(btn).toHaveAttribute("aria-expanded", "true");
    expect(btn).toHaveAttribute("data-collapsed", "false");
    expect(btn).toHaveAttribute("aria-label", "Collapse sidebar");
    expect(btn.querySelector("svg")).toBeInTheDocument();
  });

  it("collapses on click and flips aria-expanded", async () => {
    render(<SidebarToggle />);
    await userEvent.click(screen.getByTestId("sidebar-toggle"));
    const btn = screen.getByTestId("sidebar-toggle");
    expect(btn).toHaveAttribute("aria-expanded", "false");
    expect(btn).toHaveAttribute("data-collapsed", "true");
    expect(btn).toHaveAttribute("aria-label", "Expand sidebar");
    expect(localStorage.getItem("em.sidebar.collapsed")).toBe("true");
  });

  it("updates on cross-tab storage event", async () => {
    render(<SidebarToggle />);
    await act(async () => {
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "em.sidebar.collapsed",
          newValue: "true",
        }),
      );
    });
    expect(screen.getByTestId("sidebar-toggle")).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("still flips state when localStorage.setItem throws", async () => {
    const orig = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new Error("quota");
    };
    try {
      render(<SidebarToggle />);
      await userEvent.click(screen.getByTestId("sidebar-toggle"));
      expect(screen.getByTestId("sidebar-toggle")).toHaveAttribute(
        "aria-expanded",
        "false",
      );
    } finally {
      Storage.prototype.setItem = orig;
    }
  });
});
