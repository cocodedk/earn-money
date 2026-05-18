# 18. Design tokens

Typography, color, spacing, and layout dimensions. Locked between agent-em-frontend and agent-em-backend on 2026-05-18.

## Typography

| Role | Font | Size | Weight | Line height |
|------|------|------|--------|-------------|
| page title | Inter | 32px | 600 | 1.2 |
| section heading | Inter | 24px | 600 | 1.2 |
| lead | Inter | 18px | 500 | 1.4 |
| body | Inter | 16px | 400 | 1.5 |
| body-dense (tables, sidebar) | Inter | 14px | 400 | 1.4 |
| table header | Inter | 14px | 500 | 1.4 |
| caption | Inter | 12px | 400 | 1.4 |
| code, IDs, JSON, raw excerpts | JetBrains Mono | inherit | 400 | 1.5 |

Self-hosted via `@fontsource/inter` and `@fontsource/jetbrains-mono`, weights 400 / 500 / 600 only. No 700, no italics. No external CDN.

## Surface colours

| Role | Tailwind |
|------|----------|
| page background | `white` |
| sidebar background | `gray-50` |
| top-bar background | `white` |
| border / divider | `gray-200` |
| selected row tint | `blue-100` |
| hover row tint | `gray-100` |

## Text colours

| Role | Tailwind |
|------|----------|
| primary | `gray-900` |
| secondary | `gray-600` |
| muted | `gray-400` |
| link | `blue-700` |
| destructive | `red-700` |

## Brand

| Role | Tailwind |
|------|----------|
| primary button bg | `blue-600` |
| primary button hover | `blue-700` |
| primary button active | `blue-800` |
| focus ring | `ring-2 ring-blue-500 ring-offset-1` |

## Status badge colours (bg / text)

Mirrors `14-styling.md` with explicit Tailwind shades.

| Status | Background | Text |
|--------|-----------|------|
| queued | `gray-100` | `gray-700` |
| running | `blue-100` | `blue-700` |
| paused | `yellow-100` | `yellow-800` |
| stopping | `orange-100` | `orange-800` |
| stopped | `gray-100` | `gray-600` |
| failed | `red-100` | `red-700` |
| done | `green-100` | `green-700` |

## Severity badge colours (bg / text)

| Severity | Background | Text |
|----------|-----------|------|
| info | `gray-100` | `gray-700` |
| low | `blue-100` | `blue-700` |
| medium | `yellow-100` | `yellow-800` |
| high | `orange-100` | `orange-800` |
| critical | `red-100` | `red-700` |

## Spacing scale

Tailwind default (`0.25rem` increments). No custom values.

## Layout dimensions

| Element | Value |
|---------|-------|
| sidebar width | 240px |
| top bar height | 56px |
| page horizontal gutter | 24px |
| page vertical gutter | 16px |
| table row height | 40px |
| table cell horizontal padding | 12px |
| input height | 40px |
| input horizontal padding | 12px |
| button height (default) | 40px |

## Tailwind config

Tokens are surfaced via `tailwind.config.ts` `theme.extend` so CSS-Module `@apply` directives stay readable: e.g. `@apply bg-surface-sidebar text-text-primary`. Named tokens above MUST be the only place we add new shades — no ad-hoc Tailwind classes outside this table.

## Motion

No animations, per `06-scan-run-detail.md` and project-wide "plain" rule. The only motion exception is the connection-pill dot, which uses a CSS opacity transition (200ms) when transitioning between green / red. All transitions honour `prefers-reduced-motion: reduce` and shorten to 0ms.
