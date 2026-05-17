#!/bin/sh
# Push the local repo to the VPS and restart the dashboard service.
# Run from the laptop, after a clean commit. Idempotent.
#
# Defaults (override via env):
#   VPS_HOST=recon-vps        — SSH host alias from ~/.ssh/config
#   VPS_PATH=/opt/earn-money/ — install prefix on the VPS (must exist)
#   SERVICE=earn-money-dashboard
#
# Excludes mirror the gitignore intent: never push outputs, program
# state, sqlite DBs, the kill-switch flag, or platform identity.

set -eu

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log() { printf "${GREEN}[sync-vps]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[sync-vps]${NC} %s\n" "$*" >&2; }

VPS_HOST="${VPS_HOST:-recon-vps}"
VPS_PATH="${VPS_PATH:-/opt/earn-money/}"
SERVICE="${SERVICE:-earn-money-dashboard}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    warn "working tree has uncommitted changes — syncing them anyway"
fi

log "rsync  → ${VPS_HOST}:${VPS_PATH}"
rsync -az --delete \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='.mypy_cache' \
    --exclude='.pytest_cache' \
    --exclude='.ruff_cache' \
    --exclude='recon/outputs' \
    --exclude='ops/programs' \
    --exclude='*.sqlite' \
    --exclude='RECON_ENABLED' \
    --exclude='identity/platforms.md' \
    --exclude='.env' \
    --exclude='.env.bak.*' \
    ./ "${VPS_HOST}:${VPS_PATH}"

log "restart → systemd ${SERVICE}"
ssh "${VPS_HOST}" "systemctl restart ${SERVICE} && systemctl is-active ${SERVICE}"

log "done"
