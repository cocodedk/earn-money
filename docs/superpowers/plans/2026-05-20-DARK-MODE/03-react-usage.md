# React Usage

How `<ThemeToggle>` and the Settings §Theme row consume the bridge defined in [01-theme-bridge.md](./01-theme-bridge.md).

## `useSyncExternalStore`

```tsx
const snapshot = useSyncExternalStore(
  subscribeTheme,
  getThemeSnapshot,
  () => "system:light",
);
const [current, resolved] = snapshot.split(":") as [Theme, "light" | "dark"];
```

The `getServerSnapshot` fallback (`"system:light"`) is purely defensive — the app does not SSR — but vitest's React 18 hydration warning fires without it.

## Toggle cycle

The toggle computes the next persisted state from `current`, not from `resolved`:

```ts
const nextTheme: Record<Theme, Theme> = {
  light: "dark",
  dark: "system",
  system: "light",
};
```

Do not derive the next state from `resolved`. A system-dark user must still cycle `system -> light` on click, not `system -> dark` — otherwise the toggle appears stuck for any OS-dark operator.

## Settings row

```tsx
<MetaRow label="Theme">
  <span>{current}</span>{" "}
  <span style={{ color: "var(--ink-muted)" }}>
    (resolved: {resolved})
  </span>
</MetaRow>
```

The resolved suffix updates automatically when the user flips OS preference while in system mode — `subscribeTheme` fires via the `matchMedia` `change` listener.
