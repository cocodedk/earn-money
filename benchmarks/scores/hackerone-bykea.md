# Disclosure-replay scores — hackerone/bykea

- Generated: 2026-05-15T10:33:30Z
- coverage_map_version applied: 1
- Rows total: 8  (scored this pass: 8)
- Verdict counts — TP 0, FN 8, inconclusive 0, excluded 0

## Summary by vuln_class

| vuln_class | TP | FN | inconclusive | excluded | plugins |
|---|---|---|---|---|---|
| Auth-Bypass | 0 | 1 | 0 | 0 | (none) |
| IDOR | 0 | 2 | 0 | 0 | (none) |
| Info-Disclosure | 0 | 2 | 0 | 0 | nuclei, sourcemap-scan, graphql-probe |
| Logic-Flaw | 0 | 3 | 0 | 0 | (none) |

## Detail (FN first)

| verdict | vuln_class | severity | report_url | reason | eligible | source |
|---|---|---|---|---|---|---|
| FN | Info-Disclosure | medium | https://hackerone.com/reports/2209750 | plugin(s) [nuclei, sourcemap-scan, graphql-probe] cover Info-Disclosure class but hint=requires-auth requires capability we lack | 1 | scorer |
| FN | IDOR | high | https://hackerone.com/reports/2374730 | no plugin covers IDOR | 1 | scorer |
| FN | Logic-Flaw | high | https://hackerone.com/reports/2861888 | no plugin covers Logic-Flaw | 1 | scorer |
| FN | Auth-Bypass | critical | https://hackerone.com/reports/2867022 | no plugin covers Auth-Bypass | 1 | scorer |
| FN | Logic-Flaw | medium | https://hackerone.com/reports/2894018 | no plugin covers Logic-Flaw | 1 | scorer |
| FN | IDOR | medium | https://hackerone.com/reports/3085742 | no plugin covers IDOR | 1 | scorer |
| FN | Info-Disclosure | critical | https://hackerone.com/reports/3228011 | plugin(s) [nuclei, sourcemap-scan, graphql-probe] cover Info-Disclosure class but hint=requires-payload-crafting requires capability we lack | 1 | scorer |
| FN | Logic-Flaw | low | https://hackerone.com/reports/3295503 | no plugin covers Logic-Flaw | 1 | scorer |
