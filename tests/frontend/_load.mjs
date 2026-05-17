// tests/frontend/_load.mjs
// Test harness: loads a production JS file into the global scope so the
// `window.foo = ...` pattern used by the dashboard's plain <script> tags
// works in Node. Indirect eval runs the script in the global scope.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const STATIC = resolve(
  here, "..", "..", "src", "earn_money", "dashboard", "templates", "static",
);

export function loadProdScript(filename) {
  globalThis.window = globalThis;
  const src = readFileSync(resolve(STATIC, filename), "utf8");
  (0, eval)(src);
}
