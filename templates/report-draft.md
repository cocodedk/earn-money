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

## Steps to reproduce

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

<!-- Scanner evidence (do not include in the submitted report; operator deletes this section before filing):
- source_tool: {{source_tool}}
- source_run_id: {{source_run_id}}
- evidence_path: {{evidence_path}}
- nuclei signature: {{signature}}
-->
