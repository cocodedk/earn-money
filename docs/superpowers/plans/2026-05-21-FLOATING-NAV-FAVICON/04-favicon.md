---
slice: 04
title: Favicon
depends_on: []
---

# Slice 04 — favicon

Replace the missing/Vite-default tab icon with a real brand mark.

## Decision record — no Claude Code skill for favicons

I scanned the available skill list at session start (see system reminder skill block). There is **no** dedicated favicon skill bundled. Closest neighbours that are not the right tool:

- `frontend-design:frontend-design` — for general design; not a favicon generator.
- `chrome-devtools-mcp:*` — for debugging in-browser; not generation.
- `presentation-create`, `pptx`, `android-setup` — unrelated assets.

So the operator-asked question "find out if there is a good safe favicon skill on the web before creating the favicon" resolves to: **there isn't a Claude-Code skill for this, and we shouldn't add one for a one-shot asset.** The safe path is to generate locally with repo-local tooling, or to add pinned local generator tooling in the favicon commit if the repo does not already have it.

## Generator choice — local, not hosted

Web-hosted favicon generators (realfavicongenerator.net, favicon.io, faviconstudio.com) work, but all of them require uploading the source SVG. We avoid that for three reasons:

1. The mark is a brand artefact for the scanner — leaking it before public launch is unnecessary.
2. Hosted services version-bump unannounced; output bytes can change between runs (defeats deterministic builds).
3. Several generators run analytics on uploads. Even with "client-side processing" claims, validating that claim per release is overhead.

Local generator rule:

```
Do not assume `sharp`, `sharp-cli`, ImageMagick, or any global rasterizer exists.
Use repo-local tooling when present; otherwise add a pinned dev dependency in the favicon commit.
Do not use an unpinned one-shot `npx` command.
```

Preferred path when `sharp` and `png-to-ico` are already resolvable from `frontend/`, or after adding them as dev dependencies:

```
node - <<'NODE'
const fs = require("node:fs/promises");
const sharp = require("sharp");
const pngToIco = require("png-to-ico");

async function render(size) {
  return sharp("public/favicon.svg").resize(size, size).png().toBuffer();
}

async function main() {
  await sharp("public/favicon.svg").resize(32, 32).png().toFile("public/favicon-32.png");
  await sharp("public/favicon.svg").resize(180, 180).png().toFile("public/apple-touch-icon.png");
  const ico = await pngToIco(await Promise.all([16, 32, 48, 64].map(render)));
  await fs.writeFile("public/favicon.ico", ico);
}

main();
NODE
```

If the project owner rejects committed generator dev dependencies, use ImageMagick only when `magick -version` or `convert -version` succeeds locally, and record the exact command in the favicon commit message. Hosted upload generators remain out of scope.

## Source SVG

`frontend/public/favicon.svg` — hand-authored, ~30 lines, no external fonts. Visual brief:

- Square viewBox `0 0 32 32`.
- Dark canvas rounded square using the existing `--ink-strong` token value (`#0a0a0a`). Light theme tabs already use a light tab background, so a dark mark reads sharply.
- Amber bolt or shield silhouette using the existing accent token value (`#b45309`). Matches the existing operator-console accent.
- One CSS media query inside the SVG for dark-mode tabs: swap canvas to `#14130f` and accent to `#f59e0b`.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <style>
    .bg { fill: #0a0a0a; }
    .fg { fill: #b45309; }
    @media (prefers-color-scheme: dark) {
      .bg { fill: #14130f; }
      .fg { fill: #f59e0b; }
    }
  </style>
  <rect class="bg" width="32" height="32" rx="6"/>
  <!-- Operator-console mark: a thin amber EM monogram or shield -->
  <path class="fg" d="M9 9h6v3H12v3h3v3H12v3h3v0h-6V9zm8 0h6l-3 5 3 5h-3l-3-5 3-5z"/>
</svg>
```

Use the shown path as the default glyph. Only adjust it if the 16px favicon check is illegible, and keep the replacement inside the same colour, viewBox, and rounded-square constraints.

## File set

```
frontend/public/favicon.svg          ~30 lines, hand-authored
frontend/public/favicon-32.png       generated, 32×32
frontend/public/apple-touch-icon.png generated, 180×180
frontend/public/favicon.ico          generated, 16+32+48+64 multi-resolution
```

Vite serves `public/*` at the root, so paths in `index.html` are `/favicon.svg`, `/favicon.ico`, etc.

## `index.html` injection

After `<meta name="viewport">`, before the no-FOUC theme script:

```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml" sizes="any" />
<link rel="icon" href="/favicon-32.png" type="image/png" sizes="32x32" />
<link rel="alternate icon" href="/favicon.ico" sizes="16x16 32x32 48x48 64x64" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180" />
```

Four links, no `web app manifest` — this is an internal admin console, not a PWA. Adding a manifest is YAGNI here; if we ever ship a desktop install variant, that's a separate slice.

## Tests

Vitest + JSDOM can read `document.head.innerHTML`. Add a tiny `index.html` integration test (a new file, not a re-purpose of `Layout.test`):

`frontend/src/app/document-head.test.tsx`:

```ts
import { describe, it, expect } from "vitest";
import fs from "node:fs";

describe("index.html favicon links", () => {
  const html = fs.readFileSync(new URL("../../index.html", import.meta.url), "utf8");
  it("references favicon.svg", () => {
    expect(html).toMatch(/href="\/favicon\.svg"/);
  });
  it("references favicon-32.png", () => {
    expect(html).toMatch(/href="\/favicon-32\.png"/);
    expect(html).toMatch(/sizes="32x32"/);
  });
  it("references favicon.ico fallback", () => {
    expect(html).toMatch(/rel="alternate icon"/);
    expect(html).toMatch(/href="\/favicon\.ico"/);
  });
  it("references apple-touch-icon", () => {
    expect(html).toMatch(/rel="apple-touch-icon"/);
  });
});
```

This is a static-file grep, not a DOM render — appropriate because the icons are declared in `index.html`, which JSDOM doesn't load in vitest. Same approach as static-file assertions elsewhere in the suite (read the HTML on disk + regex-match the expected attributes); no shared helper exists yet, so it's an inline `fs.readFileSync`.

## Manual verification

- Open the dev server in Chromium. Tab icon shows the new mark, not Vite's lightning bolt.
- Curl: `curl -I http://localhost:5173/favicon.svg` returns `200 OK image/svg+xml`.
- Curl: `curl -I http://localhost:5173/favicon-32.png` returns `200 OK image/png`.
- Curl: `curl -I http://localhost:5173/favicon.ico` returns `200 OK image/x-icon` or `image/vnd.microsoft.icon`.
- `file frontend/public/favicon.ico` or `identify frontend/public/favicon.ico` shows 16/32/48/64px entries.
- Switch system theme; SVG re-renders with the dark palette without a reload.

## Failure modes

- **Forgetting to add `public/` to Vite.** Vite uses `public/` by convention from the project root (`frontend/`); no config change needed. If the dev server 404s on `/favicon.svg`, the dir is named wrong.
- **Hidden generator dependency.** Do not rely on a transitive package or global binary that may be missing on another machine. Either use committed dev dependencies or a verified local ImageMagick install.
- **ICO encoding bug.** Some ImageMagick builds emit single-resolution ICO. The `--define icon:auto-resize=…` flag forces multi-res. Verify with `file frontend/public/favicon.ico` — output should mention multiple sizes.
- **Cache after deploy.** Browsers aggressively cache favicons. Worth noting in the PR; a versioned query string is overkill for an internal tool.
