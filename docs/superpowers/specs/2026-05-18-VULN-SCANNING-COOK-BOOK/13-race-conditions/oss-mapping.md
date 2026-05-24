# OSS Tool Mapping — Phase 13: Race Conditions

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

### 13.01 — Double Spending

**Detects:** Concurrent requests consuming the same balance/credit twice.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| turbo-intruder | https://github.com/PortSwigger/turbo-intruder | Single-packet attack; fire N identical payment requests simultaneously |
| race-the-web | https://github.com/TheHackerDev/race-the-web | Configurable concurrent request races against payment/transfer endpoints |
| Ffuf | https://github.com/ffuf/ffuf | Parallel fuzzing mode (`-rate`) to hammer endpoint; observe response divergence |

### 13.02 — Coupon Reuse

**Detects:** Same coupon/voucher code accepted in multiple simultaneous requests.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| turbo-intruder | https://github.com/PortSwigger/turbo-intruder | Single-packet N-way race on coupon apply endpoint |
| race-the-web | https://github.com/TheHackerDev/race-the-web | Concurrent coupon redemption with response diffing |
| Wfuzz | https://github.com/xmendez/wfuzz | `--hs`/`--hh` filter to detect divergent success responses |

### 13.03 — Multiple Password Reset Use

**Detects:** Password-reset token accepted more than once when requests race.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| turbo-intruder | https://github.com/PortSwigger/turbo-intruder | Simultaneous token consumption; checks for >1 success response |
| race-the-web | https://github.com/TheHackerDev/race-the-web | Token-reuse race with configurable parallelism |
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rule for replay/reuse of single-use tokens |

### 13.04 — Limit Bypass

**Detects:** Rate or quantity limits bypassed via concurrent requests (e.g., free-tier cap).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| turbo-intruder | https://github.com/PortSwigger/turbo-intruder | High-concurrency bursts to exceed server-side counters |
| race-the-web | https://github.com/TheHackerDev/race-the-web | Parallel limit-enforcement probes with result comparison |
| Ffuf | https://github.com/ffuf/ffuf | Rapid parallel requests; `-mc` filters to catch unexpected 200s |

### 13.05 — Concurrent Order State Changes

**Detects:** Order status corrupted (e.g., paid → shipped) by simultaneous state transitions.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| turbo-intruder | https://github.com/PortSwigger/turbo-intruder | Concurrent PATCH/PUT requests targeting order state machine |
| race-the-web | https://github.com/TheHackerDev/race-the-web | Multi-endpoint race across order lifecycle endpoints |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept + replay order requests with scripted timing |

### 13.06 — Multi-Endpoint Race Bugs

**Detects:** Race windows spanning multiple distinct API endpoints (e.g., withdraw + transfer).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| turbo-intruder | https://github.com/PortSwigger/turbo-intruder | Multi-request groups in single packet; cross-endpoint timing |
| race-the-web | https://github.com/TheHackerDev/race-the-web | Targets list of endpoints concurrently; response correlation |
| Jaeles | https://github.com/jaeles-project/jaeles | Signature-based multi-step probes with parallel execution |

### 13.07 — Partial Object Creation Abuse

**Detects:** Incompletely constructed objects exploitable via concurrent read during write.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| turbo-intruder | https://github.com/PortSwigger/turbo-intruder | Race create + read requests; detect partial/inconsistent objects |
| race-the-web | https://github.com/TheHackerDev/race-the-web | Concurrent create/read pairs; flag divergent responses |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Scripted proxy to inject read requests mid-write sequence |
