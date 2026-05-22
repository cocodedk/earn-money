#!/bin/sh
# Trigger a scan on h1.cocode.dk (VPS) against a given URL.
# Run from the laptop. Manages the RECON_ENABLED flag automatically:
# creates it before dispatch, removes it after, regardless of outcome.
#
# Usage:
#   scripts/scan-on-vps.sh URL [STUB_SLUGS]
#
# Examples:
#   scripts/scan-on-vps.sh https://www.algolia.com/
#   scripts/scan-on-vps.sh https://dashboard.algolia.com/ 1.2
#   scripts/scan-on-vps.sh https://juiceshop.cocode.dk/ 1.2,1.20
#
# Env overrides:
#   VPS_HOST=recon-vps         SSH host alias
#   VPS_PATH=/opt/earn-money   stack root on the VPS

set -eu

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'
log()  { printf "${GREEN}[scan-on-vps]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[scan-on-vps]${NC} %s\n" "$*" >&2; }
fail() { printf "${RED}[scan-on-vps]${NC} %s\n" "$*" >&2; exit 1; }

[ $# -ge 1 ] || fail "usage: $0 URL [STUB_SLUGS]"
URL="$1"
STUBS="${2:-1.1,1.2,1.3,1.20}"

VPS_HOST="${VPS_HOST:-recon-vps}"
VPS_PATH="${VPS_PATH:-/opt/earn-money}"

log "target  : ${URL}"
log "stubs   : ${STUBS}"
log "via     : ${VPS_HOST}:${VPS_PATH}"

# POSIX single-quote escape: replace every `'` with `'\''` so values
# can be safely embedded inside single quotes on the remote shell.
# A URL like `https://foo'; rm -rf /` becomes `https://foo'\''; rm -rf /`
# which the remote shell parses as a single literal.
sq() { printf %s "$1" | sed "s/'/'\\\\''/g"; }
URL_E=$(sq "$URL")
STUBS_E=$(sq "$STUBS")
PATH_E=$(sq "$VPS_PATH")

# Single SSH call: enable flag → dispatch → disable flag (always).
# `trap` guarantees the flag is removed even if python errors out, so
# a stale flag never leaves the VPS armed.
ssh "${VPS_HOST}" "
set -eu
cd '${PATH_E}'
trap 'rm -f flags/RECON_ENABLED' EXIT INT TERM
echo '# scan-on-vps live smoke flag' > flags/RECON_ENABLED
docker compose exec -T backend python scripts/run_smoke.py '${URL_E}' --stubs '${STUBS_E}'
"
