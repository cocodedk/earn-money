# Cookbook Shared Schema

A paste-ready spec contract for LLM-assisted implementation. Cross-cutting types every spec and runner references. Stubs extend this with their own `<Name>Signature` / `<Name>Finding`; they never redefine the shared types below.

> **Status:** draft v0.1 — pinned to spec 1.1's persistence section. As more specs land, the shared types evolve in this file (not duplicated per stub). Bump the version when you change a shared shape.

## Shared types

### `ScanTarget`

An endpoint being scanned. One row per `(host, base_url)`.

```json
{
  "id": "uuid",
  "base_url": "https://dvwa.cocode.dk",
  "host": "dvwa.cocode.dk",
  "ip": "89.167.63.167",
  "status": "active | retired",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

### `Evidence`

Append-only observation a runner collected from a target. Findings reference one or more Evidence rows. Evidence is never silently rewritten — corrections insert a new row.

```json
{
  "id": "uuid",
  "target_id": "uuid",
  "url": "https://dvwa.cocode.dk/",
  "source": "header | cookie | html | script | css | favicon | path | meta | dns",
  "field": "Set-Cookie",
  "matched_value": "PHPSESSID",
  "raw_excerpt": "PHPSESSID=abc123; path=/",
  "content_hash": "sha256:...",
  "collected_at": "ISO-8601"
}
```

## Stub-specific pattern

Each spec defines its own `<Name>Signature` (pattern library) and `<Name>Finding` (result). The `<Name>` matches the spec's domain — e.g., spec 1.1 defines `FrameworkSignature` / `FrameworkFinding`; spec 1.7 ("Backup files") would define `BackupFileSignature` / `BackupFileFinding`. They follow these shapes.

### `<Name>Signature`

```json
{
  "id": "uuid",
  "<domain_key>": "PHP",
  "category": "<stub-defined>",
  "source": "cookie",
  "field": "name",
  "match_type": "equals | contains | contains_all | regex",
  "pattern": "PHPSESSID",
  "confidence": "low | medium | high",
  "enabled": true,
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

The `<domain_key>` is named by the stub — `technology` for framework detection, `header_name` for security-header presence checks, `secret_kind` for leaked-secrets, etc.

### `<Name>Finding`

```json
{
  "id": "uuid",
  "target_id": "uuid",
  "<domain_key>": "PHP",
  "category": "<stub-defined>",
  "confidence": "low | medium | high",
  "method": "deterministic_signature",
  "evidence_ids": ["uuid", "..."],
  "status": "candidate | confirmed | rejected | stale",
  "safe": true,
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

## Shared enums

| Name | Values |
|------|--------|
| `confidence` | `low` · `medium` · `high` |
| `status` (finding) | `candidate` · `confirmed` · `rejected` · `stale` |
| `status` (target) | `active` · `retired` |
| `method` | `deterministic_signature` (additional values added as new detection styles land) |
| `source` (evidence) | `header` · `cookie` · `html` · `script` · `css` · `favicon` · `path` · `meta` · `dns` |
| `match_type` | `equals` · `contains` · `contains_all` · `regex` |

## Invariants

- **Evidence is append-only.** Corrections insert a new row; existing rows never change.
- A finding without at least one entry in `evidence_ids` is invalid.
- A finding's `safe` field is `true` for read-only detection. Stubs that send mutations, payloads, or destructive actions MUST set `safe: false` and name the action in their spec's `## Pass/fail check`.
- A finding's `confidence` is at most the highest confidence among the signatures that produced its evidence.
- Targets are identified by `base_url`. Same host on different ports or paths counts as different targets.

## How specs reference this file

In each spec's `## Persistence` section, lead with:

> Uses shared `ScanTarget` and `Evidence` (see [`../00-shared-schema.md`](../00-shared-schema.md)).
> Stub-specific types: `<Name>Signature`, `<Name>Finding`.

Then define only the stub-specific concrete types with their own `<domain_key>` value vocabulary and `category` vocabulary. Do not restate the shared fields.

## Coding-agent rules

These are non-negotiable for any agent (LLM or human) implementing a stub against this schema.

- **Do not create new shared fields inside individual stubs.** All shared shapes live here.
- **Do not duplicate `ScanTarget` or `Evidence`.** Reference them; do not redefine.
- **If a stub needs a new shared enum value, update this file first.** Then enrich the stub.
- **Findings must always reference one or more `Evidence` rows.** A finding with empty `evidence_ids` is invalid.
- **Do not persist LLM reasoning as `Evidence`.** Evidence is a deterministic observation collected directly from a target. LLM reasoning never becomes evidence.
- **Persist LLM output only as a finding, a review note, a proposed action, or an audit record** — never as evidence and never as an automatic verdict.
- **If implementation needs a new runtime concept, define it explicitly here** rather than hiding it inside a finding's free-form field.
