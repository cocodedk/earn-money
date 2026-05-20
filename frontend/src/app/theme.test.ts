import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

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
  return await import("./theme");
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

describe("theme.ts — getTheme", () => {
  it("returns 'system' when storage is empty", async () => {
    const t = await freshImport();
    expect(t.getTheme()).toBe("system");
  });

  it("returns the stored value for 'light' / 'dark'", async () => {
    localStorage.setItem("theme", "dark");
    const t = await freshImport();
    expect(t.getTheme()).toBe("dark");
  });

  it("falls back to 'system' for invalid stored values", async () => {
    localStorage.setItem("theme", "purple");
    const t = await freshImport();
    expect(t.getTheme()).toBe("system");
  });

  it("returns 'system' when localStorage.getItem throws", async () => {
    const orig = Storage.prototype.getItem;
    Storage.prototype.getItem = () => {
      throw new Error("blocked");
    };
    try {
      const t = await freshImport();
      expect(t.getTheme()).toBe("system");
    } finally {
      Storage.prototype.getItem = orig;
    }
  });
});

describe("theme.ts — setTheme + applyTheme", () => {
  it("setTheme('light') writes storage, sets data-theme, removes .dark", async () => {
    const t = await freshImport();
    t.setTheme("light");
    expect(localStorage.getItem("theme")).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("setTheme('dark') writes storage, sets data-theme, adds .dark", async () => {
    const t = await freshImport();
    t.setTheme("dark");
    expect(localStorage.getItem("theme")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("setTheme('system') removes storage key, removes data-theme, reflects matchMedia", async () => {
    localStorage.setItem("theme", "dark");
    installMatchMedia(true);
    const t = await freshImport();
    t.setTheme("system");
    expect(localStorage.getItem("theme")).toBeNull();
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("setTheme keeps in-memory shadow on storage failure", async () => {
    const t = await freshImport();
    const orig = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new Error("quota");
    };
    try {
      t.setTheme("dark");
      expect(t.getTheme()).toBe("dark");
      expect(document.documentElement.classList.contains("dark")).toBe(true);
    } finally {
      Storage.prototype.setItem = orig;
    }
  });

  it("setTheme(<garbage>) coerces to 'system'", async () => {
    const t = await freshImport();
    (t.setTheme as (x: string) => void)("emerald");
    expect(t.getTheme()).toBe("system");
  });
});

describe("theme.ts — resolvedTheme", () => {
  it("returns the explicit value for non-system themes", async () => {
    const t = await freshImport();
    expect(t.resolvedTheme("dark")).toBe("dark");
    expect(t.resolvedTheme("light")).toBe("light");
  });

  it("follows matchMedia in system mode", async () => {
    installMatchMedia(true);
    const t = await freshImport();
    expect(t.resolvedTheme("system")).toBe("dark");
    mqMock._emit(false);
    expect(t.resolvedTheme("system")).toBe("light");
  });
});

describe("theme.ts — subscribeTheme", () => {
  it("notifies on setTheme (themechange event)", async () => {
    const t = await freshImport();
    const cb = vi.fn();
    const unsubscribe = t.subscribeTheme(cb);
    t.setTheme("dark");
    expect(cb).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it("notifies on system change ONLY when current theme is 'system'", async () => {
    installMatchMedia(false);
    const t = await freshImport();
    const cb = vi.fn();
    t.subscribeTheme(cb);
    mqMock._emit(true);
    expect(cb).toHaveBeenCalledTimes(1);
    t.setTheme("light");
    cb.mockClear();
    mqMock._emit(false);
    expect(cb).not.toHaveBeenCalled();
  });

  it("notifies + re-syncs shadow on cross-tab storage event", async () => {
    const t = await freshImport();
    const cb = vi.fn();
    t.subscribeTheme(cb);
    localStorage.setItem("theme", "dark");
    window.dispatchEvent(
      new StorageEvent("storage", { key: "theme", newValue: "dark" }),
    );
    expect(cb).toHaveBeenCalledTimes(1);
    expect(t.getTheme()).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("ignores unrelated storage events", async () => {
    const t = await freshImport();
    const cb = vi.fn();
    t.subscribeTheme(cb);
    window.dispatchEvent(new StorageEvent("storage", { key: "other" }));
    expect(cb).not.toHaveBeenCalled();
  });

  it("unsubscribe removes all listeners", async () => {
    const t = await freshImport();
    const cb = vi.fn();
    const unsubscribe = t.subscribeTheme(cb);
    unsubscribe();
    t.setTheme("dark");
    expect(cb).not.toHaveBeenCalled();
  });
});

describe("theme.ts — getThemeSnapshot", () => {
  it("returns 'current:resolved' string", async () => {
    installMatchMedia(true);
    const t = await freshImport();
    expect(t.getThemeSnapshot()).toBe("system:dark");
    t.setTheme("light");
    expect(t.getThemeSnapshot()).toBe("light:light");
  });
});
