import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

async function freshImport() {
  vi.resetModules();
  return await import("./sidebar");
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("sidebar.ts — readOnce / getSnapshot", () => {
  it("returns 'false' when storage is empty", async () => {
    const s = await freshImport();
    expect(s.getSnapshot()).toBe("false");
    expect(s.isCollapsed()).toBe(false);
  });

  it("returns 'true' when storage holds 'true'", async () => {
    localStorage.setItem("em.sidebar.collapsed", "true");
    const s = await freshImport();
    expect(s.getSnapshot()).toBe("true");
    expect(s.isCollapsed()).toBe(true);
  });

  it("falls back to 'false' on storage failure", async () => {
    const orig = Storage.prototype.getItem;
    Storage.prototype.getItem = () => {
      throw new Error("blocked");
    };
    try {
      const s = await freshImport();
      expect(s.getSnapshot()).toBe("false");
    } finally {
      Storage.prototype.getItem = orig;
    }
  });
});

describe("sidebar.ts — setCollapsed", () => {
  it("writes storage and updates snapshot", async () => {
    const s = await freshImport();
    s.setCollapsed(true);
    expect(localStorage.getItem("em.sidebar.collapsed")).toBe("true");
    expect(s.getSnapshot()).toBe("true");
  });

  it("round-trips true → false cleanly", async () => {
    const s = await freshImport();
    s.setCollapsed(true);
    s.setCollapsed(false);
    expect(localStorage.getItem("em.sidebar.collapsed")).toBe("false");
    expect(s.isCollapsed()).toBe(false);
  });

  it("keeps in-memory shadow on storage failure", async () => {
    const s = await freshImport();
    const orig = Storage.prototype.setItem;
    Storage.prototype.setItem = () => {
      throw new Error("quota");
    };
    try {
      s.setCollapsed(true);
      expect(s.isCollapsed()).toBe(true);
    } finally {
      Storage.prototype.setItem = orig;
    }
  });

  it("no-op on same value: does not emit", async () => {
    const s = await freshImport();
    const cb = vi.fn();
    s.subscribeSidebar(cb);
    s.setCollapsed(false);
    expect(cb).not.toHaveBeenCalled();
  });
});

describe("sidebar.ts — subscribeSidebar", () => {
  it("notifies on value change", async () => {
    const s = await freshImport();
    const cb = vi.fn();
    s.subscribeSidebar(cb);
    s.setCollapsed(true);
    expect(cb).toHaveBeenCalledTimes(1);
  });

  it("teardown removes the listener", async () => {
    const s = await freshImport();
    const cb = vi.fn();
    const off = s.subscribeSidebar(cb);
    off();
    s.setCollapsed(true);
    expect(cb).not.toHaveBeenCalled();
  });

  it("fires on cross-tab storage event for the right key", async () => {
    const s = await freshImport();
    const cb = vi.fn();
    s.subscribeSidebar(cb);
    window.dispatchEvent(
      new StorageEvent("storage", {
        key: "em.sidebar.collapsed",
        newValue: "true",
      }),
    );
    expect(cb).toHaveBeenCalledTimes(1);
    expect(s.getSnapshot()).toBe("true");
  });

  it("ignores unrelated storage keys", async () => {
    const s = await freshImport();
    const cb = vi.fn();
    s.subscribeSidebar(cb);
    window.dispatchEvent(new StorageEvent("storage", { key: "other" }));
    expect(cb).not.toHaveBeenCalled();
  });

  it("storage event no-op when newValue matches current", async () => {
    const s = await freshImport();
    const cb = vi.fn();
    s.subscribeSidebar(cb);
    window.dispatchEvent(
      new StorageEvent("storage", {
        key: "em.sidebar.collapsed",
        newValue: "false",
      }),
    );
    expect(cb).not.toHaveBeenCalled();
  });
});
