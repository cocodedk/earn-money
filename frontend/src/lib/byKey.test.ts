import { describe, it, expect } from "vitest";
import { byKey } from "./byKey";

type Item = { id: string; name: string };

describe("byKey", () => {
  it("returns the mapped value when the key is known", () => {
    const lookup = byKey<Item>(
      [{ id: "a", name: "Alice" }],
      (i) => i.id,
      (i) => i.name,
      (k) => k.slice(0, 8),
    );
    expect(lookup("a")).toBe("Alice");
  });

  it("returns the fallback when the key is unknown", () => {
    const lookup = byKey<Item>(
      [{ id: "a", name: "Alice" }],
      (i) => i.id,
      (i) => i.name,
      (k) => k.slice(0, 4),
    );
    expect(lookup("zzzz-foo-bar")).toBe("zzzz");
  });

  it("treats undefined items as an empty list", () => {
    const lookup = byKey<Item>(
      undefined,
      (i) => i.id,
      (i) => i.name,
      (k) => `<${k}>`,
    );
    expect(lookup("a")).toBe("<a>");
  });
});
