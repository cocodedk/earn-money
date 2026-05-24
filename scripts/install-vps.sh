#!/bin/sh
# Configure a fresh Ubuntu 24.04+ VPS for the Dockerized earn-money stack.
# Run as root on the VPS. Idempotent — safe to re-run after partial failure.
#
# Assumes:
#   - Ubuntu 24.04 LTS
#   - Outbound HTTPS to api.github.com and github.com is open
#   - You have already SSHed in as root
#
# This script does NOT:
#   - Push the repo to the VPS (use rsync from the laptop, see end-of-run notes)
#   - Transfer .env (use scp from the laptop)
#   - Touch RECON_ENABLED (that's an operator-explicit step, the consent gate)
#
# Env:
#   DRY_RUN=1              print planned privileged changes and exit
#   INSTALL_RECON_TOOLS=1  install legacy OSS recon CLIs
#   INSTALL_PASSIVE_TICK=1 enable legacy passive-tick timer

set -eu

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log() { printf "${GREEN}[install-vps]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[install-vps]${NC} %s\n" "$*" >&2; }

DRY_RUN="${DRY_RUN:-0}"

if [ "$DRY_RUN" = "1" ]; then
    log "DRY_RUN: would install apt packages: ca-certificates curl git jq rsync unzip docker.io docker-compose-plugin"
    log "DRY_RUN: would enable/start docker"
    if [ "${INSTALL_RECON_TOOLS:-0}" = "1" ]; then
        log "DRY_RUN: would install legacy OSS recon tools and wordlists"
    else
        log "DRY_RUN: would skip legacy OSS recon tools"
    fi
    log "DRY_RUN: would install/enable earn-money Docker Compose systemd unit"
    log "DRY_RUN: would install/update Caddy reverse proxy to 127.0.0.1:80"
    if [ "${INSTALL_PASSIVE_TICK:-0}" = "1" ]; then
        log "DRY_RUN: would install/enable legacy passive-tick timer"
    else
        log "DRY_RUN: would disable legacy passive-tick timer if present"
    fi
    exit 0
fi

if [ "$(id -u)" -ne 0 ]; then
    warn "must be run as root"; exit 1
fi

# Resolve the directory this script lives in so we can source helper
# libs regardless of cwd. POSIX-portable: avoids bash-only $BASH_SOURCE.
HERE=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
# shellcheck source=scripts/lib/install-vps-tools.sh
. "$HERE/lib/install-vps-tools.sh"
# shellcheck source=scripts/lib/install-vps-system.sh
. "$HERE/lib/install-vps-system.sh"

log "apt prereqs"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    ca-certificates curl git jq rsync unzip \
    docker.io docker-compose-plugin

systemctl enable --now docker >/dev/null 2>&1 || \
    warn "  docker service enable/start failed; check 'systemctl status docker'"

if [ "${INSTALL_RECON_TOOLS:-0}" = "1" ]; then
    install_pd_tools
    install_apt_tools
    install_rustscan
    install_go_tools
    install_wordlists
    print_installed_versions
else
    log "recon CLI tool install skipped (set INSTALL_RECON_TOOLS=1 to install legacy OSS tools)"
fi

install_stack_unit
install_caddy

if [ "${INSTALL_PASSIVE_TICK:-0}" = "1" ]; then
    install_passive_tick_timer
else
    log "passive-tick timer skipped (legacy v1 workflow; set INSTALL_PASSIVE_TICK=1 to enable)"
    systemctl disable --now earn-money-passive-tick.timer >/dev/null 2>&1 || true
fi

cat <<EOF

${GREEN}VPS base install complete.${NC}

Remaining steps (run from your laptop):

  1. Sync the committed repo and restart containers:
       VPS_HOST=root@<VPS> scripts/sync-vps.sh

  2. Copy .env:
       scp -p .env root@<VPS>:/opt/earn-money/.env
       ssh root@<VPS> chmod 600 /opt/earn-money/.env

  3. Arm the kill-switch when ready (explicit operator consent gate):
       ssh root@<VPS> 'mkdir -p /opt/earn-money/flags && touch /opt/earn-money/flags/RECON_ENABLED'

  4. Smoke test:
       VPS_HOST=root@<VPS> scripts/scan-on-vps.sh https://juiceshop.cocode.dk/ 1.1

EOF
