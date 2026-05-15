# Plugin idea: `apk-endpoint-extractor`

> Research note 2026-05-15. Pre-brainstorm.

## What

Static-analysis pipeline for Android `.apk` (and iOS `.ipa`) assets in scope. Downloads the package, unpacks via `apktool` / `jadx-cli`, greps decompiled output for: URL constants, endpoint patterns, hardcoded API keys, deeplinks, intent filters. Emits a structured endpoint catalogue per program.

Doesn't find bugs on its own — feeds the catalogue to other plugins (especially `idor-probe`) as a surface multiplier.

## Why

The disclosure corpus has direct prior art for "vuln found via APK analysis" on Bykea specifically: `/reports/3085742` was a hardcoded *zombie* endpoint in `com.bykea.pk` — abandoned on the server but still reachable, iterating an object ID exposed driver data. The web crawl couldn't find it because nothing on the website references it.

Mobile apps routinely contain endpoints the web doesn't expose: experimental routes, partner/admin APIs, legacy versions kept for backward compatibility, debug endpoints not removed from production builds.

## Disclosed prior art

- `hackerone/reports/3085742` — found exactly this way on Bykea's `com.bykea.pk` APK.

## Bykea-specific scope

The H1 program page lists three mobile assets (visible via the API after scope-sync). Note the committed `programs/hackerone/bykea/scope.md` in this repo has `in_scope: []` until a fresh scope-sync runs; the in-flight scope on the VPS has the populated list. Before this plugin fires against any package ID, a scope-sync must have run and the package must be confirmed present in the current in_scope list.

Candidates pending scope-sync confirmation:
- `com.bykea.pk` — rider Android (research suggests this is the listed package)
- `com.bykea.pk.partner` — driver Android
- `1351179184` — iOS App Store ID for the rider app

The Android two are direct apktool targets if confirmed in-scope. The iOS one needs an `.ipa` source — App Store decryption is out-of-scope (not authorised); only operator-supplied `.ipa` from a legitimate source.

## Shape (sketch)

- `src/earn_money/runners/apk_extract.py` — runner that takes a package ID, **gates the package ID against the program's current `scope.md` in_scope list (refuses to run if absent)**, downloads the APK only from an operator-approved legitimate source (configurable per program, defaults locked to a small allowlist), runs `jadx-cli -d <out> <apk>`, then a Python pass that greps `**/*.java` and `**/*.smali` for:
  - URL constants (`https?://\S+`)
  - Endpoint patterns (`@GET("..."), @POST("...")`, OkHttp builders, manual `$BASE_URL + "/path"`)
  - Hardcoded credentials / API keys (entropy + known-prefix filters: `AKIA`, `sk_live_`, etc.)
  - Deeplink intent filters (parses `AndroidManifest.xml`)
- Output: structured signal rows + a per-program `recon/outputs/apk/<package>.endpoints.json` artifact.

## Effort

Low — the heavy lifting is `jadx-cli` (off-the-shelf). The Python wrapper is grep + dedup + emit. Probably **a day or two of TDD**, mostly fixture wrangling.

## Prerequisites

None for the static-analysis side. Downstream consumption (`idor-probe`) is blocked on the authenticated-recon primitive.

## Hard rules

- APK source must be operator-approved + legitimate. Operator confirms `roe.md` doesn't prohibit mobile reversing for this program.
- Legal/TOS posture: **requires operator/legal confirmation before any package fetch** — distribution-mirror terms and platform TOS vary, and this is not a judgement the plugin should make autonomously. Document the operator's go/no-go per program in `programs/<platform>/<slug>/notes.md`.
- Two output kinds, each governed differently:
  - **Decompiled APK** (raw `jadx-cli` output under `recon/outputs/apk/<package>/`) — by definition contains every byte the APK contained, including any hardcoded credentials. This is inherent to decompilation; cleaning it would mean not decompiling. The protection here is location-only: `recon/outputs/` is gitignored, lives only on the VPS / operator's box, and is never re-uploaded. Operator inspects it manually if they need to verify a match.
  - **Plugin-emitted artefacts** (signal rows in `db.sqlite`, per-package `<package>.endpoints.json`, any markdown summary) — **never contain raw secret values.** For a credential match, the plugin records only: file path + line, a redacted preview (e.g. `AKIA****`), entropy/prefix fingerprint, and byte length. Sufficient for the operator to find the original in the decompiled tree without leaking it through the structured artefact surface.
- No APK, decompiled output, or plugin-emitted artefact is re-uploaded anywhere.
- iOS: only operator-supplied `.ipa` from a legitimate source confirmed by the operator. The plugin doesn't fetch `.ipa` autonomously.

## Estimated value-add

Direct catch of 1 disclosed Bykea bug; force-multiplier for `idor-probe` against several more. **Highest-ROI cheap plugin** — no authenticated-recon dependency, prior-art-proven on this program.
