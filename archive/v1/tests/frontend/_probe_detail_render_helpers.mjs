// Shared helpers for probe-detail render tests. Loads the production
// scripts under the minimal DOM shim and exposes a fresh-panel factory
// + tree walkers used by sibling *.test.mjs files.
import { loadProdScript, installDomShim } from "./_load.mjs";

installDomShim();
loadProdScript("probe-status.js");
loadProdScript("probe-state.js");
loadProdScript("probe-detail.js");

export function freshPanel() {
  installDomShim();
  const panel = document.createElement("aside");
  document._register("probe-detail", panel);
  return panel;
}

export function find(root, predicate) {
  if (predicate(root)) return root;
  for (const c of root._children || []) {
    const hit = find(c, predicate);
    if (hit) return hit;
  }
  return null;
}

export function findAll(root, predicate, acc = []) {
  if (predicate(root)) acc.push(root);
  for (const c of root._children || []) findAll(c, predicate, acc);
  return acc;
}
