# OSS Tool Mapping — Phase 10: Server-Side Request Forgery

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

## Stub Mappings

### 10.01 — Internal Service Access

**Detects:** SSRF reaching internal network services via user-controlled URL parameters

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| SSRFmap | https://github.com/swisskyrepo/SSRFmap | Primary tool; generates payloads targeting internal RFC-1918 ranges |
| ZAP | https://github.com/zaproxy/zaproxy | SSRF active scan rule; flags `url=`, `endpoint=` params |
| Nuclei | https://github.com/projectdiscovery/nuclei | `ssrf/` template pack with interactsh OOB callbacks |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz URL params with internal-address payloads |
| arjun | https://github.com/s0md3v/Arjun | Discover hidden URL/endpoint params before fuzzing |

### 10.02 — Cloud Metadata Access

**Detects:** SSRF fetching cloud metadata endpoints (169.254.169.254, IMDSv2, etc.)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| SSRFmap | https://github.com/swisskyrepo/SSRFmap | Built-in AWS/GCP/Azure metadata payloads |
| Nuclei | https://github.com/projectdiscovery/nuclei | `ssrf/cloud-metadata-*` templates for all major clouds |
| ZAP | https://github.com/zaproxy/zaproxy | SSRF rule with metadata IP range detection |
| Wfuzz | https://github.com/xmendez/wfuzz | Custom payload list with metadata URL variants |

### 10.03 — Localhost-Only Admin Interfaces

**Detects:** SSRF reaching `127.0.0.1`/`localhost` admin panels not exposed externally

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| SSRFmap | https://github.com/swisskyrepo/SSRFmap | Loopback payloads including IPv6 `::1` and decimal notation |
| Nuclei | https://github.com/projectdiscovery/nuclei | `ssrf/localhost-*` templates; common admin port probes |
| ZAP | https://github.com/zaproxy/zaproxy | SSRF active rule targeting loopback addresses |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz with localhost encodings (hex, octal, decimal IP) |

### 10.04 — URL Parser Confusion

**Detects:** Discrepancies between the server's URL parser and the fetch library (bypass via `@`, `#`, etc.)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| SSRFmap | https://github.com/swisskyrepo/SSRFmap | URL-confusion payload list (authority bypass, embedded creds) |
| Nuclei | https://github.com/projectdiscovery/nuclei | `ssrf/url-confusion-*` templates |
| Wfuzz | https://github.com/xmendez/wfuzz | Systematic fuzzing of URL parser edge cases |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and observe how server re-issues the URL |

### 10.05 — Redirect-Based SSRF

**Detects:** Server follows open redirects that chain into internal targets

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| SSRFmap | https://github.com/swisskyrepo/SSRFmap | Chained redirect payloads to internal addresses |
| ZAP | https://github.com/zaproxy/zaproxy | Open redirect + SSRF rules fire together |
| Nuclei | https://github.com/projectdiscovery/nuclei | `ssrf/redirect-*` and `redirect/` templates combined |
| Wapiti | https://github.com/wapiti-scanner/wapiti | SSRF module follows redirects to internal ranges |

### 10.06 — DNS Rebinding-Style Issues

**Detects:** Targets that resolve a hostname at check-time then fetch at request-time, allowing rebinding

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| SSRFmap | https://github.com/swisskyrepo/SSRFmap | DNS rebinding payload support with custom resolver |
| Nuclei | https://github.com/projectdiscovery/nuclei | OOB DNS interaction via interactsh for rebinding signals |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Observe DNS resolution timing vs fetch timing |

### 10.07 — Blind SSRF

**Detects:** SSRF with no in-band response — detected via OOB DNS/HTTP callbacks

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Interactsh OOB engine — primary blind SSRF detection |
| SSRFmap | https://github.com/swisskyrepo/SSRFmap | Blind mode with external collaborator URL |
| ZAP | https://github.com/zaproxy/zaproxy | Callback server (OAST) for blind detection |
| Wfuzz | https://github.com/xmendez/wfuzz | Drive payloads; pair with external listener |

### 10.08 — SSRF Through Webhooks / Importers / Previews / PDF Generators

**Detects:** Feature-level SSRF in rich upload/integration surfaces (webhooks, URL preview, PDF render)

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| SSRFmap | https://github.com/swisskyrepo/SSRFmap | Payload generation for webhook/import URL params |
| Nuclei | https://github.com/projectdiscovery/nuclei | `ssrf/` + `exposures/` templates targeting webhook endpoints |
| Playwright | https://github.com/microsoft/playwright | Drive UI-driven import/preview flows that accept URLs |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept PDF/preview requests to observe server-side fetch |
| arjun | https://github.com/s0md3v/Arjun | Discover hidden URL params in importer/webhook forms |
