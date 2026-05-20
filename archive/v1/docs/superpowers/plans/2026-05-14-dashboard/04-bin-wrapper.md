# Task 4 — `bin/dashboard`

**File:** Create `bin/dashboard` (sh, +x).

Standard wrapper that mirrors the existing `bin/queue`, `bin/show`,
`bin/apply-rules` shape: source `.env` if present, check `.venv`,
exec `python -m earn_money.dashboard.server`. Default port 8080;
operator overrides via `--port N`.

## Content

```sh
#!/bin/sh
# Thin wrapper around the dashboard server. Binds to 127.0.0.1 only.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f "$ROOT/.env" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/.env"
fi

if [ ! -x "$ROOT/.venv/bin/python" ]; then
  echo "dashboard: .venv not found at $ROOT/.venv — run 'make install-dev' first" >&2
  exit 1
fi

exec "$ROOT/.venv/bin/python" -m earn_money.dashboard.server --root "$ROOT" "$@"
```

## Operator usage

```bash
# On the VPS (or laptop) where DBs live:
bin/dashboard                  # http://127.0.0.1:8080
bin/dashboard --port 9090      # override port

# To access remotely (e.g., VPS DBs from laptop):
ssh -L 8080:localhost:8080 recon-vps
bin/dashboard                  # then open http://localhost:8080 in the laptop browser
```

## Steps

- [ ] **1. Write `bin/dashboard`** with the content above.
- [ ] **2. `chmod +x bin/dashboard`**.
- [ ] **3. Manual smoke**: `bin/dashboard --port 18080 &`, `curl
  http://127.0.0.1:18080/api/status | head` returns the JSON header,
  then `kill %1`.
- [ ] **4. `make smoke`** green (no Python changes; sanity only).
- [ ] **5. Commit** as `feat(bin): dashboard wrapper for stdlib http server`.
- [ ] **6. `/simplify`** pass.
