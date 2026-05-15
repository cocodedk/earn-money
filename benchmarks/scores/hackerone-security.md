# Disclosure-replay scores — hackerone/security

- Generated: 2026-05-15T10:33:30Z
- coverage_map_version applied: 1
- Rows total: 9  (scored this pass: 9)
- Verdict counts — TP 0, FN 8, inconclusive 1, excluded 0

## Summary by vuln_class

| vuln_class | TP | FN | inconclusive | excluded | plugins |
|---|---|---|---|---|---|
| Auth-Bypass | 0 | 1 | 0 | 0 | (none) |
| IDOR | 0 | 2 | 0 | 0 | (none) |
| Info-Disclosure | 0 | 3 | 1 | 0 | nuclei, sourcemap-scan, graphql-probe |
| SSRF | 0 | 2 | 0 | 0 | (none) |

## Detail (FN first)

| verdict | vuln_class | severity | report_url | reason | eligible | source |
|---|---|---|---|---|---|---|
| FN | Info-Disclosure | high | https://hackerone.com/reports/2032716 | plugin(s) [nuclei, sourcemap-scan, graphql-probe] cover Info-Disclosure class but hint=requires-auth requires capability we lack | 1 | scorer |
| FN | IDOR | medium | https://hackerone.com/reports/2139190 | no plugin covers IDOR | 1 | scorer |
| FN | Info-Disclosure | low | https://hackerone.com/reports/2215434 | plugin(s) [nuclei, sourcemap-scan, graphql-probe] cover Info-Disclosure class but hint=requires-business-logic requires capability we lack | 1 | scorer |
| FN | SSRF | critical | https://hackerone.com/reports/2262382 | no plugin covers SSRF | 1 | scorer |
| FN | SSRF | critical | https://hackerone.com/reports/2301565 | no plugin covers SSRF | 1 | scorer |
| FN | Info-Disclosure | high | https://hackerone.com/reports/2404415 | plugin(s) [nuclei, sourcemap-scan, graphql-probe] cover Info-Disclosure class but hint=requires-auth requires capability we lack | 1 | scorer |
| FN | Auth-Bypass | medium | https://hackerone.com/reports/2516250 | no plugin covers Auth-Bypass | 1 | scorer |
| FN | IDOR | medium | https://hackerone.com/reports/2633771 | no plugin covers IDOR | 1 | scorer |
| inconclusive | Info-Disclosure | high | https://hackerone.com/reports/3000510 | plugin(s) [nuclei, sourcemap-scan, graphql-probe] cover Info-Disclosure; hint=regex-friendly — operator review needed | 1 | scorer |
