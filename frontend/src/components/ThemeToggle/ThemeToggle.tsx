import { useSyncExternalStore } from "react";
import {
  getThemeSnapshot,
  setTheme,
  subscribeTheme,
  type Theme,
} from "../../app/theme";
import styles from "./ThemeToggle.module.css";

const NEXT: Record<Theme, Theme> = {
  light: "dark",
  dark: "system",
  system: "light",
};

const LABEL_NEXT: Record<Theme, string> = {
  light: "switch to dark",
  dark: "switch to system",
  system: "switch to light",
};

// Glyphs: sun U+2600, moon U+263E (BLACK), monitor U+25A2 — pure unicode, no
// emoji autocoloring across platforms.
const GLYPH: Record<Theme, string> = {
  light: "☀",
  dark: "☾",
  system: "▢",
};

const FALLBACK_SNAPSHOT = "system:light";

export function ThemeToggle() {
  const snapshot = useSyncExternalStore(
    subscribeTheme,
    getThemeSnapshot,
    () => FALLBACK_SNAPSHOT,
  );
  const [current] = snapshot.split(":") as [Theme, "light" | "dark"];

  return (
    <button
      type="button"
      className={styles.toggle}
      data-testid="theme-toggle"
      data-theme={current}
      aria-label={`Theme: ${current}; ${LABEL_NEXT[current]}`}
      onClick={() => setTheme(NEXT[current])}
    >
      <span aria-hidden="true">{GLYPH[current]}</span>
    </button>
  );
}
