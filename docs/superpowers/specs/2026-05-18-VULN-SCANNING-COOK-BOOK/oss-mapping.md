# OSS Tool Master Registry

> One tool list to rule them all. Phase files contain per-stub mappings;
> this file is the canonical index of every OSS tool we use or may use,
> with which phases it serves and integration priority.

## Crawler Layer (critical foundation for all phases)

These tools enable discovery — without them, scanners only see the first page.

| Tool | Repo | Role |
|------|------|------|
| Katana | https://github.com/projectdiscovery/katana | Fast JS-aware crawling |
| ZAP Spider | https://github.com/zaproxy/zaproxy | Active crawl+scan integration |
| mitmproxy | https://github.com/mitmproxy/mitmproxy | Auth-gated scriptable crawling |
| Playwright | https://github.com/microsoft/playwright | SPA/JS-heavy app crawling |
| hakrawler | https://github.com/hakluke/hakrawler | Passive crawl from link extraction |
| Wapiti | https://github.com/wapiti-scanner/wapiti | Built-in crawler + scanner |

## General Purpose Scanners

| Tool | Repo | Phases | Notes |
|------|------|--------|-------|
| ZAP | https://github.com/zaproxy/zaproxy | 01-24 | OWASP flagship; covers most phases |
| Nuclei | https://github.com/projectdiscovery/nuclei | 01-24 | Template engine; fastest to add new checks |
| Wapiti | https://github.com/wapiti-scanner/wapiti | 01,05-10,17-18,22-24 | Good breadth, Python, CLI-friendly |
| W3af | https://github.com/andresriancho/w3af | 01,04-10,23 | Plugin-based Python DAST |
| Nikto | https://github.com/sullo/nikto | 01,18,21 | Server-header and known-issue checks |

## Specialised Tools

| Tool | Repo | Primary Phases | Speciality |
|------|------|----------------|-----------|
| Sqlmap | https://github.com/sqlmapproject/sqlmap | 05 | SQL injection |
| Ghauri | https://github.com/r0oth3x49/ghauri | 05 | SQL injection (modern) |
| NoSQLMap | https://github.com/codingo/NoSQLMap | 05 | NoSQL injection |
| XSStrike | https://github.com/s0md3v/XSStrike | 06 | XSS scanner |
| Dalfox | https://github.com/hahwul/dalfox | 06 | XSS (fast, accurate) |
| Domdig | https://github.com/fcavallarin/domdig | 06,15 | DOM XSS |
| Commix | https://github.com/commixproject/commix | 05 | OS command injection |
| Tplmap | https://github.com/epinna/tplmap | 05 | SSTI |
| Fuxploider | https://github.com/almandin/fuxploider | 08 | File upload |
| LFIscanner | https://github.com/R3LI4NT/LFIscanner | 09 | LFI |
| YA-LFI | https://github.com/0x-Apollyon/YA-LFI | 09 | LFI |
| SSRFmap | https://github.com/swisskyrepo/SSRFmap | 10 | SSRF |
| CORScanner | https://github.com/chenjj/CORScanner | 16 | CORS |
| YA-CORS | https://github.com/0x-Apollyon/YA-CORS | 16 | CORS |
| smuggler | https://github.com/defparam/smuggler | 17 | HTTP smuggling |
| O-Saft | https://github.com/OWASP/O-Saft | 18,19 | TLS/SSL |
| testssl.sh | https://github.com/drwetter/testssl.sh | 18,19 | TLS/SSL |
| truffleHog | https://github.com/trufflesecurity/trufflehog | 01,15,19,21,24 | Secrets |
| gitleaks | https://github.com/gitleaks/gitleaks | 01,19,21 | Hardcoded secrets |
| jwt_tool | https://github.com/ticarpi/jwt_tool | 02,03 | JWT attacks |
| VulnAPI | https://github.com/cerberauth/vulnapi | 02,03,11,22 | JWT/OAuth/OpenAPI |
| Cherrybomb | https://github.com/blst-security/cherrybomb | 11 | OpenAPI audit |
| Akto | https://github.com/akto-api-security/community-edition | 11 | API security |
| arjun | https://github.com/s0md3v/Arjun | 05,11 | Parameter discovery |
| ParamSpider | https://github.com/devanshbatham/ParamSpider | 01,05 | Parameter mining |
| Retire.js | https://github.com/RetireJS/retire.js | 15,21 | Outdated JS libs |
| Ffuf | https://github.com/ffuf/ffuf | 01,04,11,22-24 | Fuzzing/enumeration |
| Gobuster | https://github.com/OJ/gobuster | 01,21 | Dir/DNS brute-force |
| Feroxbuster | https://github.com/epi052/feroxbuster | 01,21 | Recursive discovery |
| dirsearch | https://github.com/maurosoria/dirsearch | 01,21 | Path scanning |
| Takeover | https://github.com/edoardottt/takeover | 01,21 | Subdomain takeover |
| Tsunami | https://github.com/google/tsunami-security-scanner | 21 | Infra plugin scanner |
| Nuclei Templates | https://github.com/projectdiscovery/nuclei-templates | 01-24 | Template library |
| httpx | https://github.com/projectdiscovery/httpx | 21 | HTTP probing |

## Phase Index

| Phase | Topic | Key Tools |
|-------|-------|-----------|
| 21 | Infrastructure and Deployment Exposure | Nuclei, Gobuster, Feroxbuster, Nikto, Tsunami, truffleHog |
| 22 | Third-Party Integrations | VulnAPI, ZAP, mitmproxy, Ffuf |
| 23 | Denial of Service Within RoE | ZAP, Ffuf, Nuclei, Wapiti |
| 24 | AI/LLM-Specific Webapp Vectors | ZAP, mitmproxy, Ffuf, Playwright, truffleHog |

## Integration Priority

1. **Katana + mitmproxy** — crawl layer, must be wired first
2. **ZAP / Nuclei** — broadest coverage, easiest integration
3. **Sqlmap, Dalfox, Commix** — high-impact specialized detectors
4. **jwt_tool / VulnAPI** — auth/session family (Phases 2-3, 22)
5. **truffleHog / gitleaks** — passive secret scanning, zero-noise
6. **Ffuf / Gobuster / Feroxbuster** — discovery and fuzzing layer
7. **Tsunami / httpx** — infrastructure probing (Phase 21)
8. **Playwright** — LLM/AI agent flows and SPA-heavy targets (Phase 24)

## Source

Tool list sourced from: https://github.com/psiinon/open-source-web-scanners
Additional well-known tools added where psiinon list has gaps.
