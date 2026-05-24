# OSS Tool Mapping — Phase 03: Session Management

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
| hakrawler | https://github.com/hakluke/hakrawler | Fast passive crawl from JS/HTML/links |

## Stub Mappings

### 3.01 — Missing HttpOnly Flag

**Detects:** Session cookies served without the `HttpOnly` attribute.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule: cookie without HttpOnly flag |
| Nikto | https://github.com/sullo/nikto | Reports missing HttpOnly on session cookies |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Cookie flag analysis module |
| Nuclei | https://github.com/projectdiscovery/nuclei | `misconfiguration/` cookie flag templates |

### 3.02 — Missing Secure Flag

**Detects:** Session cookies served without the `Secure` attribute.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule: cookie without Secure flag |
| Nikto | https://github.com/sullo/nikto | Secure flag absence check |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Cookie flag analysis module |
| Nuclei | https://github.com/projectdiscovery/nuclei | Cookie security misconfiguration templates |

### 3.03 — Weak SameSite Policy

**Detects:** Session cookies with `SameSite=None` or missing SameSite directive.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule: SameSite cookie attribute analysis |
| Nuclei | https://github.com/projectdiscovery/nuclei | SameSite misconfiguration templates |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Cookie attribute enumeration |

### 3.04 — Broad Domain Cookie Scope

**Detects:** Session cookies scoped to a parent domain (`.example.com`) enabling subdomain theft.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule: overly broad cookie domain |
| Nuclei | https://github.com/projectdiscovery/nuclei | Cookie domain scope templates |

### 3.05 — Session Fixation

**Detects:** Session ID not rotated after login, allowing fixation attacks.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule: session fixation detection |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Session fixation module |
| Playwright | https://github.com/microsoft/playwright | Automate pre/post-login session ID comparison |

### 3.06 — No Session Rotation After Login

**Detects:** Same session token used before and after successful authentication.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan: compare session ID pre/post login |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Capture and diff session tokens around login |
| Playwright | https://github.com/microsoft/playwright | Automate session rotation check via browser |

### 3.07 — No Session Invalidation After Logout

**Detects:** Server-side session remains valid after logout (token replay succeeds).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active rule: replay session token after logout |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Capture session; replay after logout |
| Playwright | https://github.com/microsoft/playwright | Automate logout + replay scenario |

### 3.08 — Long-Lived Sessions

**Detects:** Session tokens with excessive TTL or no expiry set.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule: session token expiry analysis |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Inspect `Expires`/`Max-Age` on session cookies |
| jwt_tool | https://github.com/ticarpi/jwt_tool | Decode JWT `exp` claim and flag excessive TTL |

### 3.09 — JWT Algorithm Confusion

**Detects:** JWT tokens accepted with `alg:none` or RS256→HS256 confusion attacks.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| jwt_tool | https://github.com/ticarpi/jwt_tool | Full algorithm confusion test suite |
| VulnAPI | https://github.com/cerberauth/vulnapi | JWT algorithm confusion fuzzer |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan script for JWT alg:none |

### 3.10 — Weak JWT Signing Keys

**Detects:** JWT signed with a guessable or default secret key.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| jwt_tool | https://github.com/ticarpi/jwt_tool | `--crack` mode against common key wordlists |
| VulnAPI | https://github.com/cerberauth/vulnapi | Weak key detection in JWT flows |
| Ffuf | https://github.com/ffuf/ffuf | Pair with jwt_tool output to test cracked key |

### 3.11 — Missing JWT Expiry

**Detects:** JWTs issued without an `exp` claim.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| jwt_tool | https://github.com/ticarpi/jwt_tool | Decode and inspect claims; flag missing `exp` |
| VulnAPI | https://github.com/cerberauth/vulnapi | JWT claim validation checks |
| ZAP | https://github.com/zaproxy/zaproxy | Scripted passive check on JWT response |

### 3.12 — JWT Accepted After Logout

**Detects:** JWT tokens remain valid server-side after the user logs out.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| jwt_tool | https://github.com/ticarpi/jwt_tool | Replay captured JWT post-logout |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept JWT; replay after logout |
| Playwright | https://github.com/microsoft/playwright | Automate logout + JWT replay scenario |

### 3.13 — Refresh Token Abuse

**Detects:** Refresh tokens that are reusable after rotation, long-lived, or not invalidated.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Scripted active scan: replay refresh token after rotation |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and replay refresh token requests |
| VulnAPI | https://github.com/cerberauth/vulnapi | OAuth refresh token rotation tests |

### 3.14 — Session Mix-Up

**Detects:** Session data from one user visible or accessible to another (isolation failure).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Scripted multi-user context test |
| Playwright | https://github.com/microsoft/playwright | Parallel browser contexts simulating two users |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Cross-session token swap and observation |

### 3.15 — Cached Private Data

**Detects:** Authenticated responses cached by browser or CDN, exposing private data.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule: Cache-Control on sensitive responses |
| Nuclei | https://github.com/projectdiscovery/nuclei | `misconfiguration/` cache-control templates |
| Nikto | https://github.com/sullo/nikto | Reports missing `no-store` on auth pages |

### 3.16 — Concurrent Session Weakness

**Detects:** Multiple simultaneous sessions allowed without limit or notification.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Scripted multi-session active test |
| Playwright | https://github.com/microsoft/playwright | Open parallel authenticated sessions; confirm coexistence |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Hold multiple session tokens simultaneously |
