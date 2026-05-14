#!/bin/sh
# Daily passive recon tick — iterates every registered program and
# runs `scope-sync` then `passive-recon` for each. Passive only:
# no live probing of program assets. Gated by `RECON_ENABLED` so a
# missing flag silently halts the whole pass.
#
# Failures on one program don't stop the others — each invocation is
# isolated and its exit code is logged but not propagated.

set -u

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log()  { printf "${GREEN}[passive-tick]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[passive-tick]${NC} %s\n" "$*" >&2; }

ROOT="${EARN_MONEY_ROOT:-/opt/earn-money}"
cd "$ROOT" || { warn "ROOT $ROOT not found"; exit 1; }

if [ ! -f "$ROOT/RECON_ENABLED" ]; then
    warn "RECON_ENABLED missing — halting (operator-explicit kill switch)"
    exit 0
fi

log "scope-sync"
"$ROOT/bin/scope-sync" || warn "  scope-sync exited non-zero (continuing)"

# Iterate every programs/<platform>/<slug>/ that carries a scope.md.
find "$ROOT/programs" -mindepth 2 -maxdepth 2 -type d | while read -r prog_dir; do
    slug="$(basename "$prog_dir")"
    platform="$(basename "$(dirname "$prog_dir")")"
    if [ ! -f "$prog_dir/scope.md" ]; then
        continue
    fi
    if [ -f "$prog_dir/FROZEN" ]; then
        warn "  $platform/$slug FROZEN — skipping"
        continue
    fi
    log "  passive-recon $platform/$slug"
    "$ROOT/bin/passive-recon" --platform "$platform" --program "$slug" \
        || warn "    exit non-zero (continuing)"
done

log "done"
