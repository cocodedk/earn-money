#!/bin/sh
# Configure a fresh Ubuntu 24.04+ VPS for the earn-money pipeline.
# Run as root on the VPS. Idempotent — safe to re-run after partial failure.
#
# Assumes:
#   - Ubuntu 24.04 LTS (Python 3.12 already on PATH)
#   - Outbound HTTPS to api.github.com and github.com is open
#   - You have already SSHed in as root
#
# This script does NOT:
#   - Push the repo to the VPS (use rsync from the laptop, see end-of-run notes)
#   - Transfer .env (use scp from the laptop)
#   - Touch RECON_ENABLED (that's an operator-explicit step, the consent gate)

set -eu

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log() { printf "${GREEN}[install-vps]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[install-vps]${NC} %s\n" "$*" >&2; }

if [ "$(id -u)" -ne 0 ]; then
    warn "must be run as root"; exit 1
fi

# Resolve the directory this script lives in so we can source helper
# libs regardless of cwd. POSIX-portable: avoids bash-only $BASH_SOURCE.
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=lib/install-vps-tools.sh
. "$HERE/lib/install-vps-tools.sh"
# shellcheck source=lib/install-vps-system.sh
. "$HERE/lib/install-vps-system.sh"

log "apt prereqs"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3-venv python3-pip jq curl unzip ca-certificates

install_pd_tools
install_apt_tools
install_rustscan
install_go_tools
install_wordlists
install_dashboard_unit
install_caddy
install_passive_tick_timer
print_installed_versions

cat <<EOF

${GREEN}VPS base install complete.${NC} Tools at /usr/local/bin.

Remaining steps (run from your laptop):

  1. Rsync the repo (excluding gitignored + .git):
       rsync -a --delete \\
         --exclude='.venv/' --exclude='__pycache__' --exclude='.git/' \\
         --exclude='.env' --exclude='*.sqlite' --exclude='recon/outputs/' \\
         --exclude='RECON_ENABLED' --exclude='.claude/' --exclude='.mcp.json' \\
         /path/to/earn-money/ root@<VPS>:/opt/earn-money/

  2. Copy .env (CHAOS_API_TOKEN + HACKERONE_API_*):
       scp -p .env root@<VPS>:/opt/earn-money/.env
       ssh root@<VPS> chmod 600 /opt/earn-money/.env

  3. Set up the Python venv (on the VPS):
       cd /opt/earn-money
       python3 -m venv .venv
       .venv/bin/pip install -e ".[dev]" --quiet

  4. Arm the kill-switch when ready (explicit operator consent gate):
       touch /opt/earn-money/RECON_ENABLED

  5. Smoke test:
       cd /opt/earn-money && set -o allexport && . ./.env && set +o allexport
       .venv/bin/python -m earn_money.runners.passive_recon \\
         --program security --root /opt/earn-money

EOF
