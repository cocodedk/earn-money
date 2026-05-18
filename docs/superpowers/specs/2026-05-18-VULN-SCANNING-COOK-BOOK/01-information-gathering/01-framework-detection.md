---
# Managed by scripts/cookbook_progress.py — keep the `---` fences and these
# six lines intact. Values below the comments are yours to change.
phase: 1
spec: 1
slug: framework-detection
status: pending     # pending | in-progress | blocked | done
fixture: multi-target        # juice-shop | dvwa | webgoat | <name> | tbd
---

# 1.1 Framework detection

> Phase 1 — Information gathering · Category: Technology fingerprinting

<!--
GPT-5.5: Enrichment zone — paste-ready spec contract for LLM-assisted implementation.

Goal: enrich this spec so a coding agent can implement it safely and consistently.

PROTECTED — do not modify:
- YAML frontmatter (between `---` fences at top of file).
- Title heading, blockquote breadcrumb, and the `##` section headings.

EDITABLE — fill these:
- The body under each `##` section. Sub-headings (`###`), lists, code blocks, tables welcome.

OUTPUT FORMAT:
- Return raw markdown directly. Do NOT wrap the response in a ` ```markdown ` code fence.
- Inside the body, use exactly 3 backticks for code fences. No 4-backtick blocks.

CONTENT RULES:
- Use shared `ScanTarget` and `Evidence` from ../00-shared-schema.md. Do not redefine them.
- Define only stub-specific `<Name>Signature` and `<Name>Finding` types.
- Detection is deterministic. AI is `None` unless a deterministic gap is named under Safety.
- Pass/fail check has explicit assertions, including negative ones (what must NOT happen).
- Confidence: `low | medium | high`. Finding status: `candidate | confirmed | rejected | stale`.
- Never hard-code hostname → expected tech; detect from response evidence.
- Follow the Coding-agent rules in ../00-shared-schema.md.
-->

## Purpose

Detect the visible web technology stack from passive evidence. The runner uses this to understand what kind of app it is scanning before deeper tests begin.

## Inputs

<!-- What the runner receives: target URL, optional credentials, config knobs. -->

## Detection logic

Use deterministic fingerprinting only.

Allowed requests:

```text
GET /
HEAD /
GET /robots.txt
GET /sitemap.xml
GET /favicon.ico
GET linked JavaScript files from /
GET linked CSS files from /
```
Collect evidence from:

```text
HTTP headers
Set-Cookie headers
HTML body
meta generator tags
script and link tags
linked JS/CSS asset names
linked JS/CSS text
favicon hash
known product markers
```

Required scanner tools:

```text
HTTP fetcher
redirect handler
header parser
cookie parser
HTML parser
asset extractor
JS/CSS fetcher
favicon hasher
signature matcher
confidence scorer
evidence writer
finding writer
fixture test runner
```

Suggested Python packages:

```text
httpx
beautifulsoup4 or lxml
PyYAML
pydantic or jsonschema
hashlib
mmh3
pytest
```

Initial signatures:

```yaml
- id: cookie_php_session
  technology: PHP
  category: runtime
  source: cookie
  field: name
  match_type: equals
  pattern: PHPSESSID
  confidence: high

- id: cookie_java_session
  technology: Java Servlet
  category: runtime
  source: cookie
  field: name
  match_type: equals
  pattern: JSESSIONID
  confidence: high

- id: header_express
  technology: Express
  category: backend_framework
  source: header
  field: X-Powered-By
  match_type: contains
  pattern: Express
  confidence: high

- id: html_angular_marker
  technology: Angular
  category: frontend_framework
  source: html
  field: body
  match_type: contains
  pattern: ng-version
  confidence: high

- id: angular_bundle_shape
  technology: Angular SPA
  category: frontend_framework
  source: html
  field: script_names
  match_type: contains_all
  patterns:
    - runtime
    - polyfills
    - main
  confidence: medium

- id: product_dvwa_marker
  technology: DVWA
  category: known_product
  source: html
  field: body
  match_type: contains
  pattern: Damn Vulnerable Web Application
  confidence: high

- id: product_webgoat_marker
  technology: WebGoat
  category: known_product
  source: html
  field: body
  match_type: contains
  pattern: WebGoat
  confidence: high

- id: product_juiceshop_marker
  technology: OWASP Juice Shop
  category: known_product
  source: html
  field: body
  match_type: contains
  pattern: OWASP Juice Shop
  confidence: high
```

Optional comparison tools:

```text
whatweb
wappalyzer
projectdiscovery httpx
```

These tools may be used for debugging. They must not be required for the scanner to pass.

## Persistence

Create four backend records.

### ScanTarget

```json
{
  "id": "target-uuid",
  "base_url": "https://dvwa.cocode.dk",
  "host": "dvwa.cocode.dk",
  "ip": "89.167.63.167",
  "status": "active",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### FrameworkSignature

```json
{
  "id": "signature-uuid",
  "technology": "PHP",
  "category": "runtime",
  "source": "cookie",
  "field": "name",
  "match_type": "equals",
  "pattern": "PHPSESSID",
  "confidence": "high",
  "enabled": true,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### Evidence

```json
{
  "id": "evidence-uuid",
  "target_id": "target-uuid",
  "url": "https://dvwa.cocode.dk/",
  "source": "cookie",
  "field": "Set-Cookie",
  "matched_value": "PHPSESSID",
  "raw_excerpt": "PHPSESSID=abc123; path=/",
  "content_hash": "sha256...",
  "collected_at": "datetime"
}
```

Evidence is append-only during a scan.

Do not silently rewrite it.

### FrameworkFinding

```json
{
  "id": "finding-uuid",
  "target_id": "target-uuid",
  "technology": "PHP",
  "category": "runtime",
  "confidence": "high",
  "method": "deterministic_signature",
  "evidence_ids": ["evidence-uuid"],
  "status": "confirmed",
  "safe": true,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

Allowed finding statuses:

```text
candidate
confirmed
rejected
stale
```

## Safety

None.

Framework detection must be deterministic.

AI may be added later only for ambiguous evidence review. It must not create findings without deterministic evidence.

## Pass/fail check

The stub passes when all assertions are true.

```text
all three targets were scanned
only GET and HEAD were used
no login was attempted
no form was submitted
no payload was sent
at least one finding exists per target
each finding has at least one evidence record
each finding has a confidence value
each target matches its expected fixture class
no result is based on hostname hard-coding
no AI was used
```

Target-specific checks:

```text
DVWA passes if PHP, PHP session, Apache + PHP hint, or DVWA marker is detected with medium or high confidence.

WebGoat passes if Java Servlet, JSESSIONID, Spring, Spring Boot, Tomcat, or WebGoat marker is detected with medium or high confidence.

Juice Shop passes if Angular, SPA bundle structure, Node.js, Express, or OWASP Juice Shop marker is detected with medium or high confidence.
```

Example pass result:

```json
{
  "stub": "1.1-framework-detection",
  "target": "https://dvwa.cocode.dk",
  "passed": true,
  "expected_class": "php_like",
  "detected": ["PHP"],
  "required_confidence": "medium",
  "highest_confidence": "high",
  "unsafe_actions": [],
  "evidence_count": 2
}
```

## Test fixtures

Use the three local authorized fixtures behind the firewall.

```text
https://dvwa.cocode.dk
https://webgoat.cocode.dk
https://juiceshop.cocode.dk
```

Expected classes:

```text
dvwa.cocode.dk      -> PHP-like app
webgoat.cocode.dk   -> Java-like app
juiceshop.cocode.dk -> SPA / Node / Angular-like app
```

The scanner must not hard-code these hostnames to expected technologies.

It must detect them from response evidence.

## Acceptance criteria

<!-- Operational quality bar: idempotent, completes within budget, handles TLS errors gracefully, no flaky retries. -->
