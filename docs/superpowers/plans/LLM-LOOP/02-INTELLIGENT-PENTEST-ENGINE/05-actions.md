# Task 5: Add typed LLM actions

## Create

```text
src/earn_money/agent/actions.py
tests/agent/test_actions.py
```

## Requirements

The LLM may return only one typed JSON object per turn.

Allowed actions:

```json
{"tool":"get","category":"http_get","args":{"path":"/api/users","params":{"q":"test"}}}
```

```json
{"tool":"post","category":"http_post","args":{"path":"/login","json":{"email":"a@b.com","password":"x"}}}
```

```json
{"tool":"set_header","category":"auth","args":{"name":"Authorization","value":"Bearer token"}}
```

```json
{"tool":"store","category":"store_memory","args":{"kind":"token","key":"access","value":"abc"}}
```

```json
{"tool":"report_candidate","category":"report_candidate","args":{"signal_type":"idor","target":"/api/users/999","evidence":"...","confidence":"medium"}}
```

```json
{"tool":"stop","category":"stop","reason":"done"}
```

Future optional actions may be added later:

```text
graphql_introspection
openapi_probe
rate_limit_test
xss_probe
sqli_probe
file_upload_test
exploit_chain_step
```

These must remain disabled unless the RoE allows them.

## Requirements

Use strict Pydantic models.

Reject:

* malformed JSON
* unknown tools
* unknown categories
* extra fields
* missing required args
* non-string paths
* arbitrary shell commands
* arbitrary scanner names
* attempts to set base URL
* attempts to select a new host

**Important:** The LLM never sees the base URL. The `path` in args is resolved against the base URL by `HttpTool`. The LLM only provides relative paths.

## Tests

Cover:

* valid GET
* valid POST
* valid `set_header`
* valid `store`
* valid `report_candidate`
* valid `stop`
* invalid JSON fails
* unknown tool fails
* unknown category fails
* extra field fails
* shell command fails
* base URL override fails

## Acceptance

```bash
pytest tests/agent/test_actions.py -v
```

Commit:

```bash
git add src/earn_money/agent/actions.py tests/agent/test_actions.py
git commit -m "feat(agent): add strict typed LLM actions"
```
