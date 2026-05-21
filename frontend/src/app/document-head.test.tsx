import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";

const html = fs.readFileSync(
  path.resolve(process.cwd(), "index.html"),
  "utf8",
);

describe("index.html favicon links", () => {
  it("references favicon.svg", () => {
    expect(html).toMatch(/href="\/favicon\.svg"/);
    expect(html).toMatch(/type="image\/svg\+xml"/);
  });

  it("references favicon-32.png with sizes=32x32", () => {
    expect(html).toMatch(/href="\/favicon-32\.png"/);
    expect(html).toMatch(/sizes="32x32"/);
  });

  it("references favicon.ico as alternate icon", () => {
    expect(html).toMatch(/rel="alternate icon"/);
    expect(html).toMatch(/href="\/favicon\.ico"/);
  });

  it("references apple-touch-icon at 180x180", () => {
    expect(html).toMatch(/rel="apple-touch-icon"/);
    expect(html).toMatch(/sizes="180x180"/);
  });
});
