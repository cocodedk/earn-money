#!/bin/sh
# Run install-vps.sh on the VPS from the laptop. Idempotent.
#
# Usage: scripts/install-tools-vps.sh
# Env overrides:
#   VPS_HOST=recon-vps   SSH host alias from ~/.ssh/config
#   VPS_PATH=/opt/earn-money
#   DRY_RUN=1            show remote command without SSH

set -eu

VPS_HOST="${VPS_HOST:-recon-vps}"
VPS_PATH="${VPS_PATH:-/opt/earn-money}"

echo "[install-tools-vps] running install-vps.sh on $VPS_HOST"
if [ "${DRY_RUN:-0}" = "1" ]; then
    echo "[install-tools-vps] DRY_RUN: would SSH to $VPS_HOST, cd $VPS_PATH, run sh scripts/install-vps.sh"
    exit 0
fi
ssh "$VPS_HOST" sh -s -- "$VPS_PATH" <<'REMOTE'
set -eu
cd "$1"
sh scripts/install-vps.sh
REMOTE
