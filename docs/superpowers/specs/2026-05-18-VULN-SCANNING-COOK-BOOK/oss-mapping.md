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
| Wapiti | https://github.com/wapiti-scanner/wapiti | 01,05-12,17-18,21-24 | Good breadth, Python, CLI-friendly |
| W3af | https://github.com/andresriancho/w3af | 01,04-10,23 | Plugin-based Python DAST |
| Nikto | https://github.com/sullo/nikto | 01,18,19,21 | Server-header and known-issue checks |

## Specialised Tools

| Tool | Repo | Primary Phases | Speciality |
|------|------|----------------|-----------|
| Sqlmap | https://github.com/sqlmapproject/sqlmap | 05 | SQL injection |
| Ghauri | https://github.com/r0oth3x49/ghauri | 05 | SQL injection (modern) |
| NoSQLMap | https://github.com/codingo/NoSQLMap | 05 | NoSQL injection |
| Wfuzz | https://github.com/xmendez/wfuzz | 02,05,06,11,12,17 | Web fuzzer; rate/brute/param fuzzing |
| turbo-intruder | https://github.com/PortSwigger/turbo-intruder | 13 | Single-packet concurrent request races |
| race-the-web | https://github.com/TheHackerDev/race-the-web | 13 | Configurable concurrent request racing |
| WS-Attacker | https://github.com/RUB-NDS/WS-Attacker | 22 | XML signature wrapping (SAML XSW attacks) |
| garak | https://github.com/NVIDIA/garak | 24 | LLM red-teaming: prompt injection, jailbreak |
| promptfoo | https://github.com/promptfoo/promptfoo | 24 | LLM testing: adversarial prompt evaluation |
| PyRIT | https://github.com/Azure/PyRIT | 24 | LLM red-team: data exfil, indirect injection |
| XSStrike | https://github.com/s0md3v/XSStrike | 06 | XSS scanner |
| Dalfox | https://github.com/hahwul/dalfox | 06 | XSS (fast, accurate) |
| Domdig | https://github.com/fcavallarin/domdig | 06,15 | DOM XSS |
| ppmap | https://github.com/kleiton0x00/ppmap | 14 | Client-side prototype pollution |
| Commix | https://github.com/commixproject/commix | 05,08 | OS command injection |
| SSTImap | https://github.com/vladko312/SSTImap | 05 | SSTI (maintained Tplmap fork) |
| graphql-cop | https://github.com/dolevf/graphql-cop | 05,11,23 | GraphQL security testing |
| Fuxploider | https://github.com/almandin/fuxploider | 08 | File upload |
| LFIscanner | https://github.com/R3LI4NT/LFIscanner | 09 | LFI |
| YA-LFI | https://github.com/0x-Apollyon/YA-LFI | 09 | LFI |
| SSRFmap | https://github.com/swisskyrepo/SSRFmap | 10 | SSRF |
| CORScanner | https://github.com/chenjj/CORScanner | 16 | CORS |
| YA-CORS | https://github.com/0x-Apollyon/YA-CORS | 07,16 | CORS |
| smuggler | https://github.com/defparam/smuggler | 14,17 | HTTP smuggling |
| h2csmuggler | https://github.com/BishopFox/h2csmuggler | 17 | HTTP/2 cleartext upgrade smuggling |
| Jaeles | https://github.com/jaeles-project/jaeles | 13,14 | OOB/OAST-based signature scanning; deserialization callbacks |
| Web-Cache-Vulnerability-Scanner | https://github.com/Hackmanit/Web-Cache-Vulnerability-Scanner | 17 | Cache poisoning and deception |
| O-Saft | https://github.com/OWASP/O-Saft | 18,19 | TLS/SSL |
| testssl.sh | https://github.com/drwetter/testssl.sh | 18,19 | TLS/SSL |
| SSLyze | https://github.com/nabla-c0d3/sslyze | 19 | TLS/SSL (Python-native, wrappable in runners) |
| truffleHog | https://github.com/trufflesecurity/trufflehog | 01,15,19,21,24 | Secrets |
| gitleaks | https://github.com/gitleaks/gitleaks | 01,19,21 | Hardcoded secrets |
| jwt_tool | https://github.com/ticarpi/jwt_tool | 02,03,19 | JWT attacks |
| VulnAPI | https://github.com/cerberauth/vulnapi | 02,03,11,14,22 | JWT/OAuth/OpenAPI |
| Cherrybomb | https://github.com/blst-security/cherrybomb | 11,14 | OpenAPI audit |
| Akto | https://github.com/akto-api-security/community-edition | 11 | API security |
| arjun | https://github.com/s0md3v/Arjun | 05,11 | Parameter discovery |
| ParamSpider | https://github.com/devanshbatham/ParamSpider | 01,05,14 | Parameter mining |
| Retire.js | https://github.com/RetireJS/retire.js | 15,21 | Outdated JS libs |
| Ffuf | https://github.com/ffuf/ffuf | 01,04,06,11,21-24 | Fuzzing/enumeration |
| Gobuster | https://github.com/OJ/gobuster | 01,08,09,11,21 | Dir/DNS brute-force |
| Feroxbuster | https://github.com/epi052/feroxbuster | 01,11,21 | Recursive discovery |
| dirsearch | https://github.com/maurosoria/dirsearch | 01,09,11,21 | Path scanning |
| Observatory | https://github.com/mdn/mdn-http-observatory | 18 | Security headers scoring and grading |
| Takeover | https://github.com/edoardottt/takeover | 01,21 | Subdomain takeover |
| Nmap | https://github.com/nmap/nmap | 21 | Network port/service scanning; NSE scripts for debug protocol detection |
| S3Scanner | https://github.com/sa7mon/S3Scanner | 21 | Cloud bucket exposure (AWS S3, GCS, Azure Blob) |
| InQL | https://github.com/doyensec/inql | 23 | GraphQL security testing: introspection, depth-abuse, batch attacks |
| Tsunami | https://github.com/google/tsunami-security-scanner | 11,21 | Infra plugin scanner |
| Nuclei Templates | https://github.com/projectdiscovery/nuclei-templates | 01-24 | Template library |
| httpx | https://github.com/projectdiscovery/httpx | 01,11,17,18,19,21 | HTTP probing |

## Phase Index

| Phase | Topic | Key Tools |
|-------|-------|-----------|
| 01 | Information Gathering | Nuclei, Nikto, Gobuster, Feroxbuster, truffleHog, Retire.js |
| 02 | Authentication | ZAP, VulnAPI, jwt_tool, Ffuf, Wfuzz, Playwright |
| 03 | Session Management | jwt_tool, VulnAPI, ZAP, mitmproxy, Playwright |
| 04 | Access Control | ZAP, Ffuf, arjun, Nuclei, Playwright |
| 05 | Input Validation & Injection | Sqlmap, Commix, SSTImap, graphql-cop, NoSQLMap, ZAP, Wfuzz |
| 06 | Cross-Site Scripting | Dalfox, XSStrike, Domdig, ZAP, Playwright |
| 07 | CSRF & Browser-Side Request Abuse | ZAP, Wapiti, CORScanner, YA-CORS, Playwright |
| 08 | File Upload & File Handling | Fuxploider, ZAP, Nuclei, Ffuf |
| 09 | Path Traversal & File Inclusion | LFIscanner, YA-LFI, ZAP, Wapiti, Ffuf |
| 10 | Server-Side Request Forgery | SSRFmap, ZAP, Nuclei, Ffuf |
| 11 | API Security | Cherrybomb, Akto, VulnAPI, graphql-cop, ZAP, arjun, Wfuzz |
| 12 | Business Logic | ZAP, Ffuf, Wfuzz, Playwright, mitmproxy |
| 13 | Race Conditions | turbo-intruder, race-the-web, Ffuf |
| 14 | Deserialization & Object Parsing | ZAP, Nuclei, Jaeles, W3af, Cherrybomb, ppmap |
| 15 | Client-Side Security | Playwright, truffleHog, Katana, Retire.js |
| 16 | CORS & Cross-Origin Policy | CORScanner, YA-CORS, ZAP, Ffuf |
| 17 | HTTP Request/Response Handling | smuggler, h2csmuggler, Web-Cache-Vulnerability-Scanner, ZAP, Nuclei, Wfuzz |
| 18 | Security Headers & Browser Hardening | Observatory, ZAP, Nuclei, Nikto, testssl.sh |
| 19 | Cryptography & Secrets | truffleHog, gitleaks, jwt_tool, testssl.sh, SSLyze, O-Saft |
| 20 | Logging, Monitoring & Privacy | truffleHog, mitmproxy, ZAP, Playwright |
| 21 | Infrastructure & Deployment Exposure | Nmap, S3Scanner, Nuclei, Gobuster, Feroxbuster, Nikto, Tsunami, truffleHog |
| 22 | Third-Party Integrations | VulnAPI, WS-Attacker, ZAP, mitmproxy, Ffuf |
| 23 | Denial of Service Within RoE | graphql-cop, InQL, ZAP, Ffuf, Nuclei, Wapiti |
| 24 | AI/LLM-Specific Webapp Vectors | garak, promptfoo, PyRIT, mitmproxy, truffleHog |

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
