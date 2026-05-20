#!/bin/sh
# Push the local v2 scanner repo to the VPS. Run from the laptop.
# Idempotent. Destructive — `rsync --delete` wipes anything on the
# VPS path that isn't in the local tree (the v1 install at
# /opt/earn-money/ is overwritten by design; v1 lives in
# `archive/v1/` inside the v2 tree).
#
# Defaults (override via env):
#   VPS_HOST=recon-vps           — SSH host alias from ~/.ssh/config
#   VPS_PATH=/opt/earn-money/    — install prefix on the VPS
#
# Excludes mirror .gitignore: never push outputs, program state,
# sqlite DBs, the kill-switch flag, .env, or platform identity.
# v2 adds frontend/node_modules and backend caches.

set -eu

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log() { printf "${GREEN}[sync-vps]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[sync-vps]${NC} %s\n" "$*" >&2; }

VPS_HOST="${VPS_HOST:-recon-vps}"
VPS_PATH="${VPS_PATH:-/opt/earn-money/}"

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
    --exclude='node_modules' \
    --exclude='frontend/dist' \
    --exclude='recon/outputs' \
    --exclude='archive/v1/recon/outputs' \
    --exclude='*.sqlite' \
    --exclude='*.sqlite-*' \
    --exclude='flags/RECON_ENABLED' \
    --exclude='archive/v1/RECON_ENABLED' \
    --exclude='identity/platforms.md' \
    --exclude='archive/v1/identity/platforms.md' \
    --exclude='.env' \
    --exclude='.env.*' \
    --include='.env.example' \
    --exclude='.claude/' \
    --exclude='.mcp.json' \
    --exclude='.coverage' \
    --exclude='docker-compose.override.yml' \
    ./ "${VPS_HOST}:${VPS_PATH}"

log "done — v2 stack on ${VPS_HOST}:${VPS_PATH}"
log "next: ssh ${VPS_HOST} 'cd ${VPS_PATH} && docker compose up -d'"
log "       (requires docker + docker-compose-plugin on the VPS)"
