#!/bin/sh
# Trigger a scan on h1.cocode.dk (VPS) against a given URL.
# Run from the laptop. Manages the RECON_ENABLED flag automatically:
# creates it before dispatch, and removes it only if this script created it.
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
#   DRY_RUN=1                  show remote actions without SSH

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
DRY_RUN="${DRY_RUN:-0}"

log "target  : ${URL}"
log "stubs   : ${STUBS}"
log "via     : ${VPS_HOST}:${VPS_PATH}"

if [ "$DRY_RUN" = "1" ]; then
    log "DRY_RUN: would SSH to ${VPS_HOST}"
    log "DRY_RUN: would cd ${VPS_PATH}"
    log "DRY_RUN: would create flags/RECON_ENABLED only if missing"
    log "DRY_RUN: would run docker compose exec -T backend python scripts/run_smoke.py '${URL}' --stubs '${STUBS}'"
    exit 0
fi

# Single SSH call: enable flag -> dispatch -> restore flag state.
ssh "${VPS_HOST}" sh -s -- "$VPS_PATH" "$URL" "$STUBS" <<'REMOTE'
set -eu
cd "$1"
url=$2
stubs=$3

mkdir -p flags
created_flag=0
if [ ! -f flags/RECON_ENABLED ]; then
    echo '# scan-on-vps live smoke flag' > flags/RECON_ENABLED
    created_flag=1
fi

cleanup() {
    if [ "$created_flag" = "1" ]; then
        rm -f flags/RECON_ENABLED
    fi
}
trap cleanup EXIT INT TERM

docker compose exec -T backend python scripts/run_smoke.py "$url" --stubs "$stubs"
REMOTE
