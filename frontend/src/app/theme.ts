export type Theme = "light" | "dark" | "system";

const THEME_KEY = "theme";
const DARK_QUERY = "(prefers-color-scheme: dark)";
const THEME_EVENT = "themechange";

let _memTheme: Theme = readStorageOnce();

function readStorageOnce(): Theme {
  try {
    const raw = localStorage.getItem(THEME_KEY);
    return raw === "light" || raw === "dark" ? raw : "system";
  } catch {
    return "system";
  }
}

function getDarkQueryList(): MediaQueryList | null {
  try {
    return window.matchMedia ? window.matchMedia(DARK_QUERY) : null;
  } catch {
    return null;
  }
}

export function systemPrefersDark(): boolean {
  return getDarkQueryList()?.matches ?? false;
}

export function getTheme(): Theme {
  return _memTheme;
}

export function resolvedTheme(theme: Theme = getTheme()): "light" | "dark" {
  return theme === "system"
    ? systemPrefersDark()
      ? "dark"
      : "light"
    : theme;
}

export function applyTheme(theme: Theme = getTheme()): void {
  const el = document.documentElement;
  const resolved = resolvedTheme(theme);
  el.classList.toggle("dark", resolved === "dark");
  if (theme === "system") delete el.dataset.theme;
  else el.dataset.theme = theme;
}

export function setTheme(theme: Theme): void {
  const safe: Theme =
    theme === "light" || theme === "dark" || theme === "system"
      ? theme
      : "system";
  _memTheme = safe;
  try {
    if (safe === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, safe);
  } catch {}
  applyTheme(safe);
  window.dispatchEvent(new Event(THEME_EVENT));
}

export function getThemeSnapshot(): string {
  return `${getTheme()}:${resolvedTheme()}`;
}

export function subscribeTheme(callback: () => void): () => void {
  const mq = getDarkQueryList();
  const onSystemChange = () => {
    if (getTheme() === "system") {
      applyTheme("system");
      callback();
    }
  };
  const onStorage = (event: StorageEvent) => {
    if (event.key === THEME_KEY) {
      _memTheme = readStorageOnce();
      applyTheme(_memTheme);
      callback();
    }
  };
  window.addEventListener(THEME_EVENT, callback);
  window.addEventListener("storage", onStorage);
  if (mq?.addEventListener) mq.addEventListener("change", onSystemChange);
  else mq?.addListener(onSystemChange);
  return () => {
    window.removeEventListener(THEME_EVENT, callback);
    window.removeEventListener("storage", onStorage);
    if (mq?.removeEventListener) mq.removeEventListener("change", onSystemChange);
    else mq?.removeListener(onSystemChange);
  };
}
