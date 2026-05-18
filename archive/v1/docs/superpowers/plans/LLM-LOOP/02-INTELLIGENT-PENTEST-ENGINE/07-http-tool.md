# Task 7: Add safe HTTP tool

## Create or replace

```text
src/earn_money/agent/http_tool.py
tests/agent/test_http_tool.py
```

## Requirements

`HttpTool` must depend on:

* `RoePolicy`
* `ScopePolicy`
* `RequestBudget`
* `ObservationWrapper` (from Task 6)

It must support:

* GET
* POST
* `set_header`
* `decode_jwt`

It must:

* be initialized with `base_url`
* validate the action against RoE before sending traffic
* validate URL against scope before sending traffic
* check budget before sending traffic
* use `follow_redirects=False`
* manually validate redirects before following them
* reject unsafe redirects
* reject out-of-scope URLs
* reject unsupported headers
* truncate response bodies using budget
* log method, URL, status, final URL, and policy decision
* never let the model override the base URL
* **return `ObservationWrapper` for every HTTP response**

## Constructor

```python
class HttpTool:
    def __init__(
        self,
        base_url: str,
        roe_policy: RoePolicy,
        scope_policy: ScopePolicy,
        budget: RequestBudget,
    ):
        self.base_url = base_url.rstrip("/")
        self.roe_policy = roe_policy
        self.scope_policy = scope_policy
        self.budget = budget
        self.session_headers: dict[str, str] = {}
```

## Allowed headers

For v1:

```text
Authorization
Cookie
X-API-Key
Content-Type
```

## `HttpResult` (internal, not exposed to LLM directly)

```python
@dataclass
class HttpResult:
    status: int
    body: str
    headers: dict[str, str]
    final_url: str | None = None
```

## Public methods

```python
def get(self, path: str, params: dict | None = None) -> ObservationWrapper
def post(self, path: str, json: dict | None = None, data: dict | None = None) -> ObservationWrapper
def set_header(self, name: str, value: str) -> None
def decode_jwt(self, token: str) -> tuple[dict, dict] | None
```

## Tests

Cover:

* GET returns `ObservationWrapper`
* POST sends JSON body, returns `ObservationWrapper`
* header persists across calls
* unsupported header is rejected
* external URL is rejected
* unsafe redirect is rejected
* RoE-denied POST is rejected
* request over budget is rejected
* response body is truncated
* request count is recorded
* POST count is recorded
* JWT decode returns header and payload
* invalid JWT raises clean error
* returned `ObservationWrapper` has correct warning, status, URL, headers, body

## Acceptance

```bash
pytest tests/agent/test_http_tool.py -v
```

Commit:

```bash
git add src/earn_money/agent/http_tool.py tests/agent/test_http_tool.py
git commit -m "feat(agent): add RoE-aware HTTP tool with untrusted observations"
```
