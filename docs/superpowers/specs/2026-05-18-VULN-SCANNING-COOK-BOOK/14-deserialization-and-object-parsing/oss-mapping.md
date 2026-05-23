# OSS Tool Mapping — Phase 14: Deserialization and Object Parsing

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

### 14.01 — Insecure Deserialization

**Detects:** Endpoints accepting serialized objects that execute code on deserialization.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan rules for Java/PHP deserialization gadget chains |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for Java deserialization (ysoserial payloads), PHP object injection |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Module `deserialization` probes serialized object parameters |
| Jaeles | https://github.com/jaeles-project/jaeles | Custom signatures for deserialization OOB callbacks (OAST) |

### 14.02 — Unsafe YAML/XML Parsing

**Detects:** YAML unsafe-load or XML entity expansion (XXE) leading to RCE/SSRF/DoS.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | XXE active scan rule; detects external entity callbacks |
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates: `xxe-injection`, `yaml-deserialization-rce`; OAST-based OOB detection |
| Wapiti | https://github.com/wapiti-scanner/wapiti | XML/XXE module; sends crafted entity payloads |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz YAML/XML body fields with wordlist of injection strings |
| W3af | https://github.com/andresriancho/w3af | `xml_injection` plugin; entity expansion payloads |

### 14.03 — Native Binary Object Handling (Python/Java/.NET)

**Detects:** Language-native binary serialization formats accepted unsafely (Python marshal, Java Object, .NET BinaryFormatter).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates for Java deserialization gadgets; DNS/OOB callbacks |
| ZAP | https://github.com/zaproxy/zaproxy | Java deserialization scan rule; serialized object header detection |
| Jaeles | https://github.com/jaeles-project/jaeles | Custom signatures injecting gadget chain payloads with OOB verify |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Intercept binary serialized bodies; replace with crafted deserialization payloads |

### 14.04 — Prototype Pollution

**Detects:** JavaScript prototype chain poisoned via `__proto__`, `constructor.prototype` in JSON bodies or query params.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| Nuclei | https://github.com/projectdiscovery/nuclei | Templates: `prototype-pollution-*`; checks for `__proto__` reflection |
| ZAP Extensions | https://github.com/zaproxy/zap-extensions | Client-side prototype pollution passive scan |
| Domdig | https://github.com/fcavallarin/domdig | DOM-based analysis detects client-side prototype pollution sinks |
| Wfuzz | https://github.com/xmendez/wfuzz | Fuzz JSON body keys with `__proto__` variants; detect 500/behavioral diff |
| ParamSpider | https://github.com/devanshbatham/ParamSpider | Discovers query parameters that feed JSON parsers |

### 14.05 — Parser Differentials

**Detects:** Inconsistencies between front-end and back-end parsers exploitable for auth bypass or smuggling.

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Passive rules detect content-type/body parsing discrepancies |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Scriptable interception to craft ambiguous content-type bodies |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz `Content-Type` headers with conflicting values; observe divergent routing |
| smuggler | https://github.com/defparam/smuggler | Detects HTTP/1.1 `Transfer-Encoding`/`Content-Length` parser differentials |

### 14.06 — Type Confusion in JSON Body Parsing

**Detects:** Server behavior changes when JSON field types are swapped (string→int, array→string, etc.).

| Tool | Repo | Coverage Notes |
|------|------|----------------|
| ZAP | https://github.com/zaproxy/zaproxy | Active scan fuzzes JSON field types; detects 500/logic divergence |
| Wfuzz | https://github.com/xmendez/wfuzz | JSON body fuzzer with type-swap wordlists (`true`/`false`/`null`/arrays) |
| Ffuf | https://github.com/ffuf/ffuf | Fuzz body with JSON type mutation; `-mc` filters for unexpected responses |
| VulnAPI | https://github.com/cerberauth/vulnapi | OpenAPI-aware type confusion fuzzing against schema-defined fields |
| Cherrybomb | https://github.com/blst-security/cherrybomb | Static OpenAPI audit flags permissive `anyOf`/missing type constraints |
