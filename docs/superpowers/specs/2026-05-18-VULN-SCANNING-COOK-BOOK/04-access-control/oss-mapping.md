# OSS Tool Mapping — Phase 04: Access Control

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

### 4.01 — IDOR (Insecure Direct Object Reference)

**Detects:** Object identifiers in requests that can be substituted to access other users' resources.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan: IDOR via fuzzing object IDs |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz numeric/UUID IDs across authenticated endpoints |
| Wfuzz | https://github.com/xmendez/wfuzz | Parameterized ID fuzzing with auth headers |
| arjun | https://github.com/s0md3v/Arjun | Discover hidden ID parameters to fuzz |

### 4.02 — Changing Object IDs

**Detects:** Endpoints that fail to validate the authenticated user owns the referenced object.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Scripted multi-user test: swap IDs between sessions |
| Ffuf | https://github.com/ffuf/ffuf | Sequential/UUID ID enumeration with auth token A |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and modify object ID in flight |
| Playwright | https://github.com/microsoft/playwright | Automate two-account ID swap scenario |

### 4.03 — Accessing Another User's Resources

**Detects:** Direct access to another authenticated user's data via manipulated identifiers.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Multi-user context active scan |
| Ffuf | https://github.com/ffuf/ffuf | Cross-user resource enumeration |
| Wfuzz | https://github.com/xmendez/wfuzz | Auth-header swapping with target user IDs |
| Playwright | https://github.com/microsoft/playwright | Two-browser-context ownership violation test |

### 4.04 — User-to-Admin Privilege Escalation

**Detects:** Horizontal→vertical escalation by tampering role/privilege in request or token.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan: role/privilege parameter fuzzing |
| jwt_tool | https://github.com/ticarpi/jwt_tool | Modify `role`/`is_admin` claims in JWT |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz role parameter values on admin endpoints |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and modify role claim in requests |

### 4.05 — Hidden Admin APIs

**Detects:** Undocumented admin-only API endpoints discoverable via brute-force.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive brute-force with admin-path wordlists |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz `/api/admin/`, `/internal/`, `/management/` paths |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposed-panels/` admin endpoint templates |
| ZAP | https://github.com/zaproxy/zaproxy | Forced browsing active scan with non-admin session |

### 4.06 — Role Parameter Tampering

**Detects:** Role or permission values passed in request body/query that the server accepts verbatim.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan: parameter tampering on role fields |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz `role=`, `permission=`, `access_level=` params |
| Wfuzz | https://github.com/xmendez/wfuzz | Role value fuzzing with privilege wordlist |
| arjun | https://github.com/s0md3v/Arjun | Discover hidden role/privilege parameters |

### 4.07 — Cross-Tenant Object Access

**Detects:** Multi-tenant isolation failure where tenant A accesses tenant B's objects.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Multi-context active scan with different tenant sessions |
| Ffuf | https://github.com/ffuf/ffuf | Cross-tenant ID enumeration |
| Playwright | https://github.com/microsoft/playwright | Two-tenant scenario automation |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Swap tenant context in intercepted requests |

### 4.08 — Org ID Tampering

**Detects:** Organisation identifier accepted in request without server-side ownership validation.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Ffuf | https://github.com/ffuf/ffuf | Fuzz `org_id`, `organization_id`, `tenant_id` params |
| ZAP | https://github.com/zaproxy/zaproxy | Scripted parameter substitution on org-scoped endpoints |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Modify org identifiers in flight |
| arjun | https://github.com/s0md3v/Arjun | Discover hidden org-scope parameters |

### 4.09 — Workspace Switching Bugs

**Detects:** Workspace/context switch that grants access to another user's workspace data.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Scripted workspace-switch active test |
| Playwright | https://github.com/microsoft/playwright | Automate workspace switch with attacker token |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept workspace-switch request; swap IDs |

### 4.10 — Hidden UI Buttons but Exposed APIs

**Detects:** Actions hidden in the UI for low-privilege users but accessible via direct API call.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Forced browsing + scripted low-priv API calls |
| Feroxbuster | https://github.com/epi052/feroxbuster | Discover API paths not linked in the UI |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz API paths with low-privilege session |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Capture admin-session API traffic; replay with user token |

### 4.11 — Missing Backend Permission Checks

**Detects:** Endpoints that enforce access control only client-side; server ignores auth/role.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan: call protected endpoints without auth header |
| Ffuf | https://github.com/ffuf/ffuf | Unauthenticated + low-priv requests to all discovered paths |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Auth bypass via missing server-side check detection |

### 4.12 — Unsafe Direct API Calls

**Detects:** Internal/service APIs exposed to the public internet without auth enforcement.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposed-panels/` + `misconfiguration/` internal API templates |
| Feroxbuster | https://github.com/epi052/feroxbuster | Discover `/internal/`, `/service/`, `/rpc/` paths |
| httpx | https://github.com/projectdiscovery/httpx | Probe discovered paths without auth; flag 200s |

### 4.13 — Private File Exposure

**Detects:** Private uploads or user files accessible without authentication/authorization.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Ffuf | https://github.com/ffuf/ffuf | Fuzz upload paths with predictable filename patterns |
| Feroxbuster | https://github.com/epi052/feroxbuster | Recursive discovery of upload/media directories |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/files/` upload directory listing templates |
| ZAP | https://github.com/zaproxy/zaproxy | Forced browsing to private file paths |

### 4.14 — Predictable Download URLs

**Detects:** File download URLs with sequential IDs or guessable components.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Ffuf | https://github.com/ffuf/ffuf | Sequential/integer ID enumeration on download endpoints |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan: IDOR on download endpoints |
| arjun | https://github.com/s0md3v/Arjun | Discover hidden download parameters for fuzzing |

### 4.15 — Signed URL Misuse

**Detects:** Pre-signed URLs that lack expiry, scope restriction, or IP binding.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Scripted test: replay signed URL after TTL; strip signature |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Capture signed URL; replay from different context |
| Nuclei | https://github.com/projectdiscovery/nuclei | Signed URL validation misconfiguration templates |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz signed URL parameters (path, expiry, token) |
