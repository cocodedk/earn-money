# OSS Tool Mapping — Phase 18: Security Headers and Browser Hardening

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

### 18.01 — Missing Content-Security-Policy

**Detects:** Absence or weak `Content-Security-Policy` header enabling XSS and data injection.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Observatory | https://github.com/mozilla/http-observatory | CSP presence and strength grading |
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10038 (CSP missing/weak) |
| Nikto | https://github.com/sullo/nikto | Flags missing CSP header |
| Nuclei | https://github.com/projectdiscovery/nuclei | `missing-csp` / `csp-misconfiguration` templates |
| httpx | https://github.com/projectdiscovery/httpx | Extract `Content-Security-Policy` from responses |

### 18.02 — Missing HSTS

**Detects:** Absent or short-max-age `Strict-Transport-Security` header allowing downgrade attacks.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| testssl.sh | https://github.com/drwetter/testssl.sh | HSTS check including max-age and preload |
| Observatory | https://github.com/mozilla/http-observatory | HSTS presence, max-age ≥ 6 months, preload check |
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10035 (HSTS missing) |
| Nikto | https://github.com/sullo/nikto | Flags missing HSTS |
| Nuclei | https://github.com/projectdiscovery/nuclei | `missing-hsts` templates |

### 18.03 — Missing X-Frame-Options / frame-ancestors

**Detects:** Absent framing controls enabling classic clickjacking.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10020 (X-Frame-Options missing) |
| Observatory | https://github.com/mozilla/http-observatory | X-Frame-Options + CSP frame-ancestors check |
| Nikto | https://github.com/sullo/nikto | Flags missing X-Frame-Options |
| Nuclei | https://github.com/projectdiscovery/nuclei | `missing-x-frame-options` templates |
| httpx | https://github.com/projectdiscovery/httpx | Bulk header extraction for missing value |

### 18.04 — Missing Referrer-Policy

**Detects:** Absent `Referrer-Policy` leaking sensitive URL fragments to third parties.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Observatory | https://github.com/mozilla/http-observatory | Referrer-Policy presence and value strength |
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule for missing Referrer-Policy |
| Nikto | https://github.com/sullo/nikto | Flags absence of Referrer-Policy |
| Nuclei | https://github.com/projectdiscovery/nuclei | `missing-referrer-policy` templates |

### 18.05 — Missing Permissions-Policy

**Detects:** Absent `Permissions-Policy` (formerly Feature-Policy) leaving browser APIs ungated.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Observatory | https://github.com/mozilla/http-observatory | Permissions-Policy presence check |
| ZAP | https://github.com/zaproxy/zaproxy | Passive scan rule for missing Permissions-Policy |
| Nuclei | https://github.com/projectdiscovery/nuclei | `missing-permissions-policy` templates |
| httpx | https://github.com/projectdiscovery/httpx | Bulk header presence check |

### 18.06 — Weak Cookie Attributes

**Detects:** Cookies missing `Secure`, `HttpOnly`, or `SameSite` attributes enabling theft/CSRF.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rules 10010/10011 (cookie attribute checks) |
| Observatory | https://github.com/mozilla/http-observatory | Cookie attribute scoring |
| Wapiti | https://github.com/wapiti-scanner/wapiti | `--module cookieflags` cookie attribute module |
| Nuclei | https://github.com/projectdiscovery/nuclei | `cookie-without-httponly` / `cookie-without-secure` |
| Nikto | https://github.com/sullo/nikto | Reports insecure cookie flags |

### 18.07 — MIME Sniffing Allowed

**Detects:** Absent `X-Content-Type-Options: nosniff` enabling MIME-type confusion attacks.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule 10021 (X-Content-Type-Options missing) |
| Nikto | https://github.com/sullo/nikto | Flags absent nosniff header |
| Observatory | https://github.com/mozilla/http-observatory | X-Content-Type-Options check |
| Nuclei | https://github.com/projectdiscovery/nuclei | `missing-x-content-type-options` templates |
| httpx | https://github.com/projectdiscovery/httpx | Bulk header extraction |

### 18.08 — Clickjacking Exposure

**Detects:** Pages renderable in frames via absent/permissive framing headers, confirmed with a framing PoC.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active rule 10020 + clickjacking PoC generation |
| Nuclei | https://github.com/projectdiscovery/nuclei | `clickjacking` template family |
| Playwright | https://github.com/microsoft/playwright | Iframe rendering test to confirm frame load |
| Observatory | https://github.com/mozilla/http-observatory | Combined framing-header check |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Clickjacking module checks framing headers |
