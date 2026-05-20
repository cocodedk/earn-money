import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx,css,module.css}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        display: ['"Funnel Display"', "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ['"Funnel Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
