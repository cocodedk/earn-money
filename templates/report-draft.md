---
finding_hash: {{finding_hash}}
platform: {{platform}}
slug: {{slug}}
vuln_class: {{vuln_class}}
asset: {{asset}}
target: {{target}}
severity_hint: {{severity_hint}}
source_tool: {{source_tool}}
first_seen: {{first_seen}}
---

# {{title}}

## Summary

[**Operator: rewrite this paragraph.** State the vulnerability in one sentence: what it is, where it lives, and what an attacker can do.]

## Affected asset

- URL: `{{target}}`
- Asset: `{{asset}}`

## Steps to Reproduce

[**Operator: replace with real manual steps.** The scanner found something; you must confirm it actually exploits. List the exact requests / clicks an attacker takes.]

1. ...
2. ...
3. ...

## Impact

[**Operator: write this in your own words.** What an attacker gains. Not the scanner's severity hint — your assessment after manual verification.]

## Proof of concept

[**Operator: one redacted screenshot or curl command.** No PII. Stop after one — per CLAUDE.md hard rule.]

## Suggested remediation

[**Operator: optional.** A one-paragraph fix suggestion if obvious. Otherwise omit.]

---

> **SCANNER EVIDENCE — DELETE BEFORE FILING.**
> The lines below are scanner internals (template ID, raw artifact path, etc.).
> They do not belong in the submitted report. Delete this entire section
> (from the line above through to the end of this file) before pasting
> into HackerOne.

```
source_tool: {{source_tool}}
source_run_id: {{source_run_id}}
evidence_path: {{evidence_path}}
signature: {{signature}}
```
