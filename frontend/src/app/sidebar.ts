const KEY = "em.sidebar.collapsed";
type Collapsed = "true" | "false";

const listeners = new Set<() => void>();
let _mem: Collapsed = readOnce();

function readOnce(): Collapsed {
  try {
    if (typeof window === "undefined") return "false";
    const v = window.localStorage.getItem(KEY);
    return v === "true" ? "true" : "false";
  } catch {
    return "false";
  }
}

function emit(): void {
  listeners.forEach((cb) => cb());
}

if (typeof window !== "undefined") {
  window.addEventListener("storage", (e) => {
    if (e.key !== KEY) return;
    const next: Collapsed = e.newValue === "true" ? "true" : "false";
    if (next === _mem) return;
    _mem = next;
    emit();
  });
}

export function isCollapsed(): boolean {
  return _mem === "true";
}

export function setCollapsed(next: boolean): void {
  const v: Collapsed = next ? "true" : "false";
  if (v === _mem) return;
  _mem = v;
  try {
    window.localStorage.setItem(KEY, v);
  } catch {}
  emit();
}

export function subscribeSidebar(cb: () => void): () => void {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
}

export function getSnapshot(): string {
  return _mem;
}
