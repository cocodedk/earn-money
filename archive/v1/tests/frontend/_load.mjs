// tests/frontend/_load.mjs
// Test harness: loads a production JS file into the global scope so the
// `window.foo = ...` pattern used by the dashboard's plain <script> tags
// works in Node. Uses `vm.Script` with the source filename set so Node's
// --experimental-test-coverage tracks lines in the production file.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { Script } from "node:vm";

const here = dirname(fileURLToPath(import.meta.url));
const STATIC = resolve(
  here, "..", "..", "src", "earn_money", "dashboard", "templates", "static",
);

export function loadProdScript(filename) {
  globalThis.window = globalThis;
  const filepath = resolve(STATIC, filename);
  const src = readFileSync(filepath, "utf8");
  new Script(src, { filename: filepath }).runInThisContext();
}

// Minimal DOM shim — just enough for probe-detail.js / probe-render.js
// rendering tests. No real layout, no event bubbling. Each call to
// installDomShim() resets state so test isolation works.
export function installDomShim() {
  const nodes = new Map();

  function makeNode(tag) {
    return {
      tagName: tag,
      className: "",
      textContent: "",
      dataset: {},
      classList: {
        _set: new Set(),
        add(...cs) { for (const c of cs) this._set.add(c); },
        contains(c) { return this._set.has(c); },
      },
      _children: [],
      _listeners: {},
      firstChild: null,
      appendChild(child) { this._children.push(child); this.firstChild = this._children[0]; return child; },
      removeChild(child) {
        this._children = this._children.filter((c) => c !== child);
        this.firstChild = this._children[0] || null;
        return child;
      },
      addEventListener(name, fn) { (this._listeners[name] = this._listeners[name] || []).push(fn); },
      _click() { for (const fn of (this._listeners.click || [])) fn(); },
      get children() { return this._children; },
    };
  }

  globalThis.document = {
    createElement: (tag) => makeNode(tag),
    getElementById: (id) => nodes.get(id) || null,
    _register(id, node) { nodes.set(id, node); return node; },
    _clear() { nodes.clear(); },
  };
}
