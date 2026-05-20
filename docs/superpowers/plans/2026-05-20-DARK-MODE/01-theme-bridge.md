# Theme Bridge Contract

This file makes the DOM, storage, no-FOUC, and React subscription behavior executable without guessing. It complements [00-overview.md](./00-overview.md).

## DOM model

- `data-theme` stores only explicit user overrides: `"light"` or `"dark"`.
- Missing `data-theme` means "system"; CSS media queries decide the token values.
- `.dark` stores the resolved theme for Tailwind `dark:` selectors.
- The bridge must update both attributes together in the inline script and in React.

| State | `localStorage.theme` | `data-theme` | `.dark` |
| --- | --- | --- | --- |
| forced light | `"light"` | `"light"` | absent |
| forced dark | `"dark"` | `"dark"` | present |
| system + OS light | missing/invalid | absent | absent |
| system + OS dark | missing/invalid | absent | present |

Invalid stored values are treated as system mode. Do not persist `"system"`; remove the key.

## No-FOUC inline script

Place this in `index.html` inside `<head>`, before the module script that mounts React. If there is a static stylesheet link in the head, put this script before that link too.

```html
<script>
  (function () {
    var root = document.documentElement;
    var stored = null;
    var dark = false;

    try {
      stored = localStorage.getItem("theme");
    } catch (e) {}

    if (stored === "dark" || stored === "light") {
      root.dataset.theme = stored;
      dark = stored === "dark";
    } else {
      delete root.dataset.theme;
      try {
        dark = !!(window.matchMedia &&
          window.matchMedia("(prefers-color-scheme: dark)").matches);
      } catch (e) {}
    }

    root.classList.toggle("dark", dark);
  })();
</script>
```

Rationale: `data-theme` handles CSS tokens; `.dark` handles Tailwind variants. Setting only one of them creates a visible mismatch before React runs.

## `theme.ts` API

`theme.ts` maintains a tab-lifetime in-memory shadow (`_memTheme`) so `getTheme()` returns a consistent value even when `localStorage` is blocked or `setItem` throws. The shadow is initialized from storage at module load (best-effort); `setTheme()` writes the shadow synchronously, then attempts the storage write. Storage failures degrade gracefully — this tab still works correctly, only cross-tab sync is lost (consistent with [00-overview.md §Mechanism](./00-overview.md)).

```ts
// frontend/src/app/theme.ts
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

export function getTheme(): Theme {
  return _memTheme;
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

export function resolvedTheme(theme: Theme = getTheme()): "light" | "dark" {
  return theme === "system"
    ? (systemPrefersDark() ? "dark" : "light")
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
  // Runtime guard for JS callers / devtools-from-console misuse:
  // anything other than the three valid values resets to "system".
  const safe: Theme =
    theme === "light" || theme === "dark" || theme === "system"
      ? theme
      : "system";

  // Update the in-memory shadow FIRST so getTheme() stays consistent
  // with the DOM/event even if the storage write below throws.
  _memTheme = safe;

  try {
    if (safe === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, safe);
  } catch {
    // Storage blocked / quota exceeded — this tab still works correctly
    // (in-memory shadow drives the bridge); cross-tab storage events
    // won't fire for this change. Acceptable degradation.
  }

  applyTheme(safe);
  window.dispatchEvent(new Event(THEME_EVENT));
}
```

Implementation note: this is browser-only app code. Tests may import it in JSDOM; stub `window.matchMedia` where needed.

## Subscription contract

`ThemeToggle` should use `useSyncExternalStore` with a real external-store subscription. The store must notify on:
- `setTheme()` calls in this tab.
- OS theme changes while the user is in system mode.
- `storage` events from another tab changing `theme`.

```ts
export function getThemeSnapshot(): string {
  const theme = getTheme();
  return `${theme}:${resolvedTheme(theme)}`;
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
      // Re-sync the in-memory shadow from storage (cross-tab change).
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
```

If project tests run in a JSDOM version without `matchMedia`, this contract falls back to resolved light/system behavior; tests that need dark system mode should still install a per-test stub.

## React usage

React-side consumption (`<ThemeToggle>`, Settings row) lives in [03-react-usage.md](./03-react-usage.md).
