# OSS Tool Mapping — Phase 02: Authentication

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

### 2.01 — Username Enumeration

**Detects:** Differential responses on login/registration/reset that confirm username existence.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule: username enumeration via timing/message |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Differential response detection on login forms |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz username field; filter by response size/code |
| Wfuzz | https://github.com/xmendez/wfuzz | Username brute with response diff filtering |

### 2.02 — Weak Password Policy

**Detects:** Registration/change endpoints that accept trivially weak passwords.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule; manual active test via scripting |
| Wfuzz | https://github.com/xmendez/wfuzz | Submit weak password payloads; check acceptance |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz password field with common-weak wordlist |

### 2.03 — Missing Account Lockout

**Detects:** Login endpoints that allow unlimited password attempts without lockout.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan: brute-force test with lockout detection |
| Wfuzz | https://github.com/xmendez/wfuzz | High-volume credential fuzzing; observe 429/lockout absence |
| Ffuf | https://github.com/ffuf/ffuf | Rapid login attempts to confirm no lockout |

### 2.04 — Weak Rate Limiting

**Detects:** Auth endpoints that fail to throttle requests adequately.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Ffuf | https://github.com/ffuf/ffuf | High-rate requests; confirm no 429 or delay |
| Wfuzz | https://github.com/xmendez/wfuzz | Rate-probe payloads on login/reset endpoints |
| ZAP | https://github.com/zaproxy/zaproxy | Scripted active scan for rate-limit absence |

### 2.05 — Predictable Reset Tokens

**Detects:** Password-reset tokens with low entropy or sequential patterns.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Token analysis via Sequencer tool |
| Ffuf | https://github.com/ffuf/ffuf | Enumerate token space if token is short/sequential |
| Wfuzz | https://github.com/xmendez/wfuzz | Brute-force token range on reset endpoint |

### 2.06 — Token Reuse After Reset

**Detects:** Reset tokens that remain valid after already being used.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Scripted active scan: replay used token |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept + replay reset request with used token |
| Playwright | https://github.com/microsoft/playwright | Automate token reuse flow in browser |

### 2.07 — Weak Token Expiry

**Detects:** Reset or session tokens that remain valid far beyond reasonable TTL.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Scripted scan: use old token after delay |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Replay intercepted token after TTL window |

### 2.08 — Reset Poisoning (Host Header)

**Detects:** Password-reset link generation that trusts attacker-controlled `Host` header.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active rule: Host header injection on reset flow |
| Nuclei | https://github.com/projectdiscovery/nuclei | `vulnerabilities/` host-header injection templates |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Host header manipulation module |

### 2.09 — Account Takeover via Email Change

**Detects:** Flows where email change can be abused without re-authentication or token verification.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Scripted active scan on account-settings flow |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and tamper email-change request |
| Playwright | https://github.com/microsoft/playwright | Automate full email-change ATO scenario |

### 2.10 — Authentication Bypass

**Detects:** Logic flaws allowing access to authenticated resources without valid credentials.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan: forced browsing + auth bypass checks |
| Nuclei | https://github.com/projectdiscovery/nuclei | `vulnerabilities/` auth-bypass templates |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Auth bypass via HTTP verb tampering module |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz auth headers/cookies with null/empty values |

### 2.11 — Missing MFA on Sensitive Flows

**Detects:** High-risk actions (payment, email change, password change) lacking MFA step.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rule + scripted flow audit |
| Playwright | https://github.com/microsoft/playwright | Automate sensitive-action flows and check for MFA challenge |

### 2.12 — Weak Recovery Codes

**Detects:** MFA recovery codes that are short, sequential, or reusable.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Sequencer analysis on generated recovery codes |
| Ffuf | https://github.com/ffuf/ffuf | Brute-force short recovery code space |

### 2.13 — MFA Reset Abuse

**Detects:** MFA bypass via account recovery flow that skips the MFA requirement.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Scripted flow test: recovery path skips MFA |
| Playwright | https://github.com/microsoft/playwright | Automate recovery flow and assert MFA enforcement |

### 2.14 — OAuth Redirect URI Issues

**Detects:** OAuth `redirect_uri` validation flaws (open redirect, URI manipulation).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| VulnAPI | https://github.com/cerberauth/vulnapi | OAuth redirect_uri fuzzing |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan: redirect_uri manipulation |
| Nuclei | https://github.com/projectdiscovery/nuclei | `exposures/` + OAuth misconfiguration templates |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz redirect_uri parameter values |

### 2.15 — Missing OAuth State Parameter

**Detects:** OAuth flows that omit or do not validate the `state` parameter (CSRF risk).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| VulnAPI | https://github.com/cerberauth/vulnapi | OAuth state parameter validation checks |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule: CSRF on OAuth callback |
| Nuclei | https://github.com/projectdiscovery/nuclei | OAuth state-missing detection templates |

### 2.16 — OAuth Token Substitution

**Detects:** Accepting access tokens issued for other clients/audiences.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| VulnAPI | https://github.com/cerberauth/vulnapi | Token substitution test cases |
| jwt_tool | https://github.com/ticarpi/jwt_tool | Craft and substitute JWT tokens across audiences |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and swap tokens between sessions |

### 2.17 — OAuth Account Linking Flaws

**Detects:** Account linking flows that allow takeover via pre-linking attacker account.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| VulnAPI | https://github.com/cerberauth/vulnapi | Account linking flow audits |
| ZAP | https://github.com/zaproxy/zaproxy | Scripted scan of linking endpoints |
| Playwright | https://github.com/microsoft/playwright | Automate pre-linking attack scenario |

### 2.18 — Login CSRF

**Detects:** Login forms lacking CSRF protection, allowing forced login as attacker.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active rule: CSRF on login form |
| Wapiti | https://github.com/wapiti-scanner/wapiti | CSRF module covers login endpoints |
| Nuclei | https://github.com/projectdiscovery/nuclei | Login CSRF detection templates |

### 2.19 — Duplicate Account Confusion

**Detects:** Case/whitespace normalization flaws creating duplicate accounts exploitable for ATO.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Ffuf | https://github.com/ffuf/ffuf | Fuzz username with case/whitespace variants |
| Playwright | https://github.com/microsoft/playwright | Automate duplicate registration scenario |

### 2.20 — Email Verification Bypass

**Detects:** Endpoints accessible or account features usable before email verification.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan: access protected endpoints pre-verification |
| Playwright | https://github.com/microsoft/playwright | Automate unverified account flow |
| Ffuf | https://github.com/ffuf/ffuf | Force-browse verified-only paths with unverified session |

### 2.21 — Invitation Abuse

**Detects:** Invitation tokens that are reusable, guessable, or not tied to the invitee.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Sequencer on invitation tokens |
| Ffuf | https://github.com/ffuf/ffuf | Enumerate token space if low entropy |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and replay invitation token |

### 2.22 — Tenant/Org Join Abuse

**Detects:** Flaws in multi-tenant join flows allowing unauthorized org membership.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Scripted active scan of join/invite endpoints |
| Playwright | https://github.com/microsoft/playwright | Automate cross-tenant join abuse scenario |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz org/tenant identifiers on join endpoints |
