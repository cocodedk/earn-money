import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

type MediaQueryListMock = {
  matches: boolean;
  media: string;
  addEventListener: (type: "change", cb: (e: { matches: boolean }) => void) => void;
  removeEventListener: (type: "change", cb: (e: { matches: boolean }) => void) => void;
  addListener: (cb: (e: { matches: boolean }) => void) => void;
  removeListener: (cb: (e: { matches: boolean }) => void) => void;
  _emit: (matches: boolean) => void;
};

let mqMock: MediaQueryListMock;

function installMatchMedia(initialDark: boolean) {
  const listeners = new Set<(e: { matches: boolean }) => void>();
  mqMock = {
    matches: initialDark,
    media: "(prefers-color-scheme: dark)",
    addEventListener: (_t, cb) => listeners.add(cb),
    removeEventListener: (_t, cb) => listeners.delete(cb),
    addListener: (cb) => listeners.add(cb),
    removeListener: (cb) => listeners.delete(cb),
    _emit: (matches) => {
      mqMock.matches = matches;
      listeners.forEach((cb) => cb({ matches }));
    },
  };
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation(() => mqMock),
  });
}

async function freshImport() {
  vi.resetModules();
  return await import("./ThemeToggle");
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.classList.remove("dark");
  installMatchMedia(false);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ThemeToggle", () => {
  it("renders with data-testid and the system glyph on a fresh load", async () => {
    const { ThemeToggle } = await freshImport();
    render(<ThemeToggle />);
    const btn = screen.getByTestId("theme-toggle");
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("data-theme", "system");
    expect(btn.textContent).toBe("▢");
  });

  it("aria-label reflects both current and next state", async () => {
    const { ThemeToggle } = await freshImport();
    render(<ThemeToggle />);
    expect(screen.getByTestId("theme-toggle")).toHaveAccessibleName(
      "Theme: system; switch to light",
    );
  });

  it("cycle: system -> light", async () => {
    const { ThemeToggle } = await freshImport();
    render(<ThemeToggle />);
    await userEvent.click(screen.getByTestId("theme-toggle"));
    const btn = screen.getByTestId("theme-toggle");
    expect(btn).toHaveAttribute("data-theme", "light");
    expect(btn.textContent).toBe("☀");
    expect(btn).toHaveAccessibleName("Theme: light; switch to dark");
    expect(localStorage.getItem("theme")).toBe("light");
  });

  it("cycle: light -> dark", async () => {
    localStorage.setItem("theme", "light");
    const { ThemeToggle } = await freshImport();
    render(<ThemeToggle />);
    await userEvent.click(screen.getByTestId("theme-toggle"));
    const btn = screen.getByTestId("theme-toggle");
    expect(btn).toHaveAttribute("data-theme", "dark");
    expect(btn.textContent).toBe("☾");
    expect(localStorage.getItem("theme")).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("cycle: dark -> system", async () => {
    localStorage.setItem("theme", "dark");
    const { ThemeToggle } = await freshImport();
    render(<ThemeToggle />);
    await userEvent.click(screen.getByTestId("theme-toggle"));
    const btn = screen.getByTestId("theme-toggle");
    expect(btn).toHaveAttribute("data-theme", "system");
    expect(btn.textContent).toBe("▢");
    expect(localStorage.getItem("theme")).toBeNull();
  });

  it("does not include 'system' as a literal label when in light mode", async () => {
    localStorage.setItem("theme", "light");
    const { ThemeToggle } = await freshImport();
    render(<ThemeToggle />);
    expect(screen.getByTestId("theme-toggle")).toHaveAccessibleName(
      "Theme: light; switch to dark",
    );
  });

  it("re-renders without unmount when system matchMedia changes in system mode", async () => {
    const { ThemeToggle } = await freshImport();
    render(<ThemeToggle />);
    const btn = screen.getByTestId("theme-toggle");
    // Glyph stays "system" because current theme is unchanged.
    act(() => mqMock._emit(true));
    expect(screen.getByTestId("theme-toggle")).toBe(btn);
    expect(btn).toHaveAttribute("data-theme", "system");
  });

  it("unmount cleans up the theme subscription", async () => {
    const { ThemeToggle } = await freshImport();
    const { unmount } = render(<ThemeToggle />);
    unmount();
    // After unmount, dispatching a themechange must not throw or update DOM.
    expect(() =>
      window.dispatchEvent(new Event("themechange")),
    ).not.toThrow();
    expect(screen.queryByTestId("theme-toggle")).not.toBeInTheDocument();
  });

  it("two rapid clicks advance two steps (system -> light -> dark)", async () => {
    const { ThemeToggle } = await freshImport();
    render(<ThemeToggle />);
    const btn = screen.getByTestId("theme-toggle");
    await userEvent.click(btn);
    await userEvent.click(btn);
    expect(btn).toHaveAttribute("data-theme", "dark");
    expect(localStorage.getItem("theme")).toBe("dark");
  });
});
