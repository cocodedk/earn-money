#!/bin/sh
# Run install-vps.sh on the VPS from the laptop. Idempotent.
#
# Usage: scripts/install-tools-vps.sh
# Env overrides:
#   VPS_HOST=recon-vps   SSH host alias from ~/.ssh/config
#   VPS_PATH=/opt/earn-money

set -eu

VPS_HOST="${VPS_HOST:-recon-vps}"
VPS_PATH="${VPS_PATH:-/opt/earn-money}"

echo "[install-tools-vps] running install-vps.sh on $VPS_HOST"
ssh "$VPS_HOST" "bash '$VPS_PATH/scripts/install-vps.sh'"
