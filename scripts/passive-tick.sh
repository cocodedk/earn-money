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

if [ ! -x "$ROOT/bin/scope-sync" ] || [ ! -x "$ROOT/bin/passive-recon" ]; then
    warn "legacy v1 passive tick requires $ROOT/bin/scope-sync and $ROOT/bin/passive-recon"
    warn "current Docker stack uses API/Celery scans; passive tick is disabled for this checkout"
    exit 1
fi

if [ ! -d "$ROOT/programs" ]; then
    warn "programs directory missing: $ROOT/programs"
    exit 1
fi

if [ ! -f "$ROOT/RECON_ENABLED" ] && [ ! -f "$ROOT/flags/RECON_ENABLED" ]; then
    warn "RECON_ENABLED missing — halting (operator-explicit kill switch)"
    exit 0
fi

log "scope-sync (per program)"
find "$ROOT/programs" -mindepth 2 -maxdepth 2 -type d | while read -r prog_dir; do
    slug="$(basename "$prog_dir")"
    platform="$(basename "$(dirname "$prog_dir")")"
    [ -f "$prog_dir/scope.md" ] || continue
    if [ -f "$prog_dir/FROZEN" ]; then
        warn "  $platform/$slug FROZEN — skipping"
        continue
    fi
    log "  scope-sync $platform/$slug"
    "$ROOT/bin/scope-sync" --platform "$platform" --program "$slug" \
        || warn "    exit non-zero — runner is responsible for freezing"
done

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
