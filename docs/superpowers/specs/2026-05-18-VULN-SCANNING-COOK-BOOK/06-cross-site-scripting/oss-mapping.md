# OSS Tool Mapping — Phase 06: Cross-Site Scripting

> Maps each stub to proven OSS tools. Our platform wraps these for orchestration,
> result normalization, and persistence. Do not re-implement detection logic already
> covered by a mature OSS tool.

## Crawler Layer (critical — required by all stubs)

| Tool | Repo | Why |
|------|------|-----|
| Katana | https://github.com/projectdiscovery/katana | Fast JS-aware endpoint discovery |
| ZAP Spider | https://github.com/zaproxy/zaproxy | Passive+active crawl integrated with scanning |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Scriptable proxy for auth-gated crawling |
| Playwright | https://github.com/microsoft/playwright | JS-heavy SPA crawling with real browser |
| hakrawler | https://github.com/hakluke/hakrawler | Fast passive crawl from JS/HTML links |
| ParamSpider | https://github.com/devanshbatham/ParamSpider | Parameter mining from Wayback/JS for reflection targets |

## Stub Mappings

### 6.01 — Query Parameter Reflection

**Detects:** Reflected XSS via URL query parameters

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Dalfox | https://github.com/hahwul/dalfox | Fast reflected XSS; param-level analysis with DOM check |
| XSStrike | https://github.com/s0md3v/XSStrike | Context-aware payload generation |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 40012/40014 |

### 6.02 — Path Reflection

**Detects:** Reflected XSS in URL path segments

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Dalfox | https://github.com/hahwul/dalfox | Path segment fuzzing mode |
| ffuf | https://github.com/ffuf/ffuf | Path-segment fuzzing with XSS wordlists |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 40012 |

### 6.03 — Header Reflection

**Detects:** Reflected XSS via HTTP request headers (User-Agent, Referer, X-* headers)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Dalfox | https://github.com/hahwul/dalfox | Custom header injection with blind payloads |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz arbitrary HTTP headers with XSS payloads |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 40012 with header vector |

### 6.04 — Stored XSS in Comments

**Detects:** Stored XSS injected via comment/review input fields

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 40016 (persistent XSS) |
| Dalfox | https://github.com/hahwul/dalfox | Blind stored XSS via callback |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module permanentxss` |

### 6.05 — Stored XSS in Profiles

**Detects:** Stored XSS in user profile fields (bio, name, avatar URL)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 40016; authenticated session |
| Dalfox | https://github.com/hahwul/dalfox | Blind stored XSS via callback URL |

### 6.06 — Stored XSS in Admin Panels

**Detects:** Stored XSS surfaced in admin-only views from user-supplied data

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Authenticated scan with admin session; rule 40016 |
| Dalfox | https://github.com/hahwul/dalfox | Blind callback confirms admin-context execution |

### 6.07 — Stored XSS in Support Tickets

**Detects:** Stored XSS in ticket body/attachments rendered to support agents

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Dual-session scan (user submit / agent view) |
| Dalfox | https://github.com/hahwul/dalfox | Blind callback fires when agent views ticket |

### 6.08 — Stored XSS in Logs Viewed in Dashboard

**Detects:** Stored XSS in log/audit entries rendered in a web dashboard

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Dalfox | https://github.com/hahwul/dalfox | Blind callback confirms dashboard execution |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 40016 with privileged session |

### 6.09 — Unsafe JavaScript Sinks

**Detects:** DOM XSS via dangerous sinks: innerHTML, eval, location.href assignments

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Domdig | https://github.com/fcavallarin/domdig | Purpose-built DOM XSS scanner (headless Chrome) |
| Dalfox | https://github.com/hahwul/dalfox | DOM sink analysis mode |
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10028 + DOM XSS script |

### 6.10 — URL Fragment Handling

**Detects:** DOM XSS via location.hash fragment parsed client-side

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Domdig | https://github.com/fcavallarin/domdig | Fragment-based DOM XSS with headless execution |
| Playwright | https://github.com/microsoft/playwright | Navigate with malicious fragments; observe DOM mutations |

### 6.11 — postMessage Misuse

**Detects:** XSS or data leakage via poorly validated window.postMessage handlers

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Playwright | https://github.com/microsoft/playwright | Inject cross-origin postMessage; observe handler |
| Domdig | https://github.com/fcavallarin/domdig | DOM analysis of message event handlers |

### 6.12 — Stored XSS via HTML Body

**Detects:** Stored XSS in rich-text fields that render raw HTML

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| XSStrike | https://github.com/s0md3v/XSStrike | HTML context-aware payload generation |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule 40016 |
| Dalfox | https://github.com/hahwul/dalfox | Blind stored with HTML body payloads |

### 6.13 — XSS via HTML Attributes

**Detects:** XSS injected into attribute values (onload=, onerror=, href=javascript:)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Dalfox | https://github.com/hahwul/dalfox | Attribute-context XSS payloads |
| XSStrike | https://github.com/s0md3v/XSStrike | Context-aware: detects attribute vs tag position |

### 6.14 — XSS via JavaScript Strings

**Detects:** XSS injected into JS string literals (breaking out with quote characters)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Dalfox | https://github.com/hahwul/dalfox | JS-string context detection and breakout payloads |
| Domdig | https://github.com/fcavallarin/domdig | Runtime execution verification via headless Chrome |

### 6.15 — XSS via Template Literals

**Detects:** XSS through backtick template literal injection in client-side code

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Dalfox | https://github.com/hahwul/dalfox | Template literal breakout payloads |
| Playwright | https://github.com/microsoft/playwright | Inject and observe runtime eval in template literals |

### 6.16 — XSS via SVG

**Detects:** XSS via uploaded or inlined SVG containing script or onload handlers

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Fuxploider | https://github.com/almandin/fuxploider | SVG upload with embedded script payloads |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan detects SVG reflected in response |
| Nuclei | https://github.com/projectdiscovery/nuclei | `svg-xss` upload templates |

### 6.17 — Missing CSP

**Detects:** Absence of a Content-Security-Policy header

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10038 (missing CSP) |
| Nikto | https://github.com/sullo/nikto | Reports missing security headers including CSP |
| Nuclei | https://github.com/projectdiscovery/nuclei | `missing-csp` header-check templates |

### 6.18 — Unsafe-Inline in CSP

**Detects:** CSP present but weakened by unsafe-inline or unsafe-eval directives

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10055 (CSP scanner) |
| Nuclei | https://github.com/projectdiscovery/nuclei | `csp-unsafe-inline` templates |

### 6.19 — Weak Script Sources in CSP

**Detects:** CSP script-src allowing CDNs, wildcards, or data: URIs that enable bypass

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10055 (CSP scanner) |
| Nuclei | https://github.com/projectdiscovery/nuclei | `csp-wildcard` / `csp-bypass` templates |

### 6.20 — JSONP or Callback Bypasses

**Detects:** JSONP endpoints or callback= params that allow CSP/SOP bypass or data exfil

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan; JSONP-specific passive rules |
| Nuclei | https://github.com/projectdiscovery/nuclei | `jsonp` and `open-redirect-jsonp` templates |
| ffuf | https://github.com/ffuf/ffuf | Fuzz callback / jsonp / cb parameters |
