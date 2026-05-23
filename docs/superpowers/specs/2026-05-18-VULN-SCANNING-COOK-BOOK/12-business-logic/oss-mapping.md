# OSS Tool Mapping — Phase 12: Business Logic

> Maps each stub to proven OSS tools. Our platform wraps these for orchestration,
> result normalization, and persistence. Do not re-implement detection logic already
> covered by a mature OSS tool.
>
> Note: business-logic flaws are inherently application-specific. OSS tools provide
> transport and fuzzing primitives; the detection heuristics must be written in our
> platform's stub layer on top of those primitives.

## Crawler Layer (critical — required by all stubs)

| Tool | Repo | Why |
|------|------|-----|
| Katana | https://github.com/projectdiscovery/katana | Fast JS-aware endpoint discovery |
| ZAP Spider | https://github.com/zaproxy/zaproxy | Passive+active crawl integrated with scanning |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Scriptable proxy for auth-gated crawling |
| Playwright | https://github.com/microsoft/playwright | JS-heavy SPA crawling with real browser |
| hakrawler | https://github.com/hakluke/hakrawler | Fast passive crawl from JS/HTML links |

## Stub Mappings

### 12.01 — Skipping Required Steps

**Detects:** Workflows where a step can be omitted and a later step still succeeds

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan replays out-of-order requests; multi-step flow tests |
| Playwright | https://github.com/microsoft/playwright | Script multi-step flows; skip steps; assert end-state |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and drop step requests; observe if flow continues |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz step-sequencing tokens/nonces |

### 12.02 — Direct API Calls Out of Order

**Detects:** API endpoints that accept out-of-sequence calls bypassing the intended flow

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Replay captured requests in arbitrary order |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Reorder and replay captured API call sequences |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz state-bearing parameters with prior-step values |
| Akto | https://github.com/akto-api-security/community-edition | Flow-sequence API test support |

### 12.03 — Quantity Tampering

**Detects:** Order/cart quantities accepted as negative, zero, or extremely large values

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan fuzzes numeric fields with boundary values |
| Wfuzz | https://github.com/xmendez/wfuzz | Payload lists: 0, -1, -999, MAX_INT, float values |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Integer fuzzing via HTTP parameter module |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and rewrite quantity fields in transit |

### 12.04 — Coupon Abuse

**Detects:** Coupon codes that can be stacked, reused, or applied beyond stated limits

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Replay coupon application requests multiple times |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz coupon fields; test repeat application |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept coupon requests; replay across sessions |
| Playwright | https://github.com/microsoft/playwright | Drive UI coupon flows; test stacking in real browser |

### 12.05 — Negative Values

**Detects:** Fields accepting negative monetary/quantity values to gain credit or bypass limits

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Numeric fuzzing with negative boundary payloads |
| Wfuzz | https://github.com/xmendez/wfuzz | Systematic negative/zero/fractional payload lists |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Rewrite numeric fields to negative values in transit |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Parameter fuzzing module covers negative int edge cases |

### 12.06 — Currency Mismatch

**Detects:** Prices accepted in a cheap currency but charged/credited in a strong currency

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and swap currency codes in payment requests |
| Playwright | https://github.com/microsoft/playwright | Drive currency-selection UI; observe server-side currency used |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan injects alternative currency codes |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz currency fields with ISO-4217 code wordlist |

### 12.07 — Race Between States

**Detects:** TOCTOU / race conditions where parallel requests exploit a brief valid window

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan concurrent request mode for race detection |
| Wfuzz | https://github.com/xmendez/wfuzz | `--threads` mode for simultaneous identical requests |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Script synchronized parallel replay of captured requests |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates using `race: true` protocol attribute for concurrent send |

### 12.08 — Invalid Transitions

**Detects:** State machines that accept transitions not permitted by the business rules

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Replay requests that attempt forbidden state transitions |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept state-change requests; inject invalid target states |
| Playwright | https://github.com/microsoft/playwright | Drive UI to an intermediate state; attempt forbidden transitions |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz status/state enum fields with invalid values |

### 12.09 — Self-Approval

**Detects:** Workflows where the requester can also approve their own request

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Multi-session test: same token used for create and approve |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Single-session replay of submit then approve with same auth |
| Playwright | https://github.com/microsoft/playwright | Script create-then-approve flow within one authenticated context |

### 12.10 — Role Confusion

**Detects:** Actions that succeed under a role lacking the required permission

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Multi-session role comparison; access control test suite |
| Akto | https://github.com/akto-api-security/community-edition | Role-based access control automated test matrix |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Swap session tokens between roles; replay privileged requests |
| Nuclei | https://github.com/projectdiscovery/nuclei | `idor/` + `access-control/` templates |

### 12.11 — Stale Permissions

**Detects:** Permissions that remain active after a role change, de-provisioning, or session expiry

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Session-expiry test; replay old token after revocation |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Replay captured requests with revoked credentials |
| Playwright | https://github.com/microsoft/playwright | Automate role-change then re-test previously allowed actions |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates probing revocation endpoints with expired token replay |

### 12.12 — Trial Abuse

**Detects:** Trial/free-tier limits bypassable by re-registration or account manipulation

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan on account-creation and trial-start flows |
| Playwright | https://github.com/microsoft/playwright | Automate multi-account trial re-enroll flows |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept trial-activation requests; replay with new identifiers |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz trial-tracking fields (email, device ID, IP) |

### 12.13 — Invitation Abuse

**Detects:** Invitation links/codes reusable beyond their intended single-use or scope

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Replay invitation acceptance requests; test reuse |
| Wfuzz | https://github.com/xmendez/wfuzz | Enumerate and fuzz invitation token space |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Capture invite token; replay multiple times |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom templates probing invitation token endpoints with enumerated code payloads |

### 12.14 — Quota Bypass

**Detects:** Rate/usage quotas bypassable via parameter manipulation or account switching

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan fuzzes quota-tracking fields |
| Wfuzz | https://github.com/xmendez/wfuzz | High-volume requests to trigger and then bypass quota |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept quota-check requests; modify quota identifiers |
| Nuclei | https://github.com/projectdiscovery/nuclei | Custom `misconfiguration/` templates for quota bypass patterns |

### 12.15 — Refund / Credit Abuse

**Detects:** Refund or credit flows that can be exploited to gain more value than the original purchase

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Replay refund requests; test double-refund scenarios |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept and replay refund/credit API calls |
| Playwright | https://github.com/microsoft/playwright | Automate purchase-refund-repurchase flows to detect credit leaks |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz refund amount and order ID fields |
