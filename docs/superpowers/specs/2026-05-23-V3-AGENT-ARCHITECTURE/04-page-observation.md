# PageObservation Schema

The controller produces a normalized `PageObservation` after every browser action. The LLM
never sees raw HTML dumps or arbitrary selectors — only a structured, redacted view with
controller-assigned IDs.

## Inclusion policy

Controller-decided baseline + LLM-requested expansion. The controller always includes core
elements; the LLM can request more via `observe_page` args (e.g.
`{include_screenshot: true, element_ids: ["form_1"]}`). Controller may deny or downgrade.

After the first observation, prefer deltas: new routes, changed elements, new errors, new
network calls. Full observations are stored in persistence; compact deltas are sent to the LLM.
The controller can reconstruct full state from the DB even if the prompt only included deltas.

## Schema

```yaml
PageObservation:
  id: "obs_17"
  turn: 7
  phase: "enumerate"
  action_ref: "act_16"

  page:
    url_ref: "url_4"
    path: "/login"
    title: "Login"
    origin_label: "target"
    load_state: "networkidle"
    page_hash: "..."

  elements:
    links:
      - id: "link_3"
        text: "Forgot password?"
        accessible_name: "Forgot password"
        href_ref: "url_8"
        visible: true
    buttons:
      - id: "btn_2"
        text: "Sign in"
        aria_role: "button"
        accessible_name: "Sign in"
        enabled: true
    forms:
      - id: "form_1"
        method: "POST"
        action_ref: "url_9"
        fields:
          - id: "field_1"
            label: "Email"
            type: "email"
            required: true
          - id: "field_2"
            label: "Password"
            type: "password"
            required: true
    inputs:
      - id: "input_5"
        label: "Search"
        type: "text"
        required: false
        value_state: "empty"   # empty | filled | redacted

  visible_text:
    blocks:
      - id: "txt_1"
        text: "Email"
        role_context: "form_label"

  discovered:
    routes:
      - id: "url_8"
        path: "/forgot-password"
        source: "link"
    assets:
      - id: "asset_2"
        path: "/main.js"
        type: "script"
        interesting_refs: ["/score-board"]

  selected_html_excerpts:
    - id: "html_1"
      reason: "script tag references app bundle"
      trust: "untrusted_target_content"
      excerpt: '<script src="/main.js"></script>'

  network:
    entries:
      - id: "req_12"
        method: "GET"
        path: "/login"
        status: 200
        resource_type: "document"
        content_type: "text/html"
        redirect_chain: []

  browser_state:
    cookies:
      - name: "session"
        domain: "target"
        path: "/"
        secure: true
        httponly: true
        samesite: "Lax"
    storage_keys:
      - type: "localStorage"
        key: "theme"

  console:
    messages:
      - level: "error"
        text: "Failed to load resource"
        source_ref: "req_14"

  screenshot:
    artifact_ref: null
    reason: null

  meta:
    observed_at: "..."
    response_bytes: 18420
    truncated: false
    redactions: ["cookie_values", "password_fields"]
```

## Security rules

- No cookie values — only names and flags
- No raw selectors exposed — controller maps IDs to Playwright locators internally
- URL refs / relative paths — never arbitrary full URLs with different hosts
- HTML excerpts marked `untrusted_target_content`
- Screenshot as external artifact ref, never inline bytes
- Input `value_state` is `empty` | `filled` | `redacted` — never raw sensitive values

## Auto-screenshot triggers

Controller attaches screenshots automatically when:
- Failed click/fill action
- Modal, captcha, or error state detected
- Visual change without structural change
- Checkpoint or evidence capture moment
- Page changed visually but DOM diff is minimal

## Other observation types

`AgentObservation.observation_type` supports five values: `page`, `http`, `stub`, `tool`,
`asset`. This file documents the `page` type. The remaining types (`http` for raw HTTP
responses, `stub` for v2 stub results, `tool` for OSS tool output, `asset` for
`inspect_asset` results) will be specified when their corresponding actions are implemented
(stubs/tools post-slice-1, asset in slice 1 as a simplified JSON excerpt structure).
