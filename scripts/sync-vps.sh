#!/bin/sh
# Push git-tracked files to the VPS and rebuild containers.
# Idempotent. Destructive — rsync --delete removes stale tracked
# files but protects VPS-only runtime files (.env, overrides, flags).
#
# Defaults (override via env):
#   VPS_HOST=recon-vps           — SSH host alias from ~/.ssh/config
#   VPS_PATH=/opt/earn-money/    — install prefix on the VPS
#
# Deploys from `git archive HEAD` so only committed, tracked files
# reach the VPS. Uncommitted changes and untracked files are excluded.

set -eu

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { printf "${GREEN}[sync-vps]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[sync-vps]${NC} %s\n" "$*" >&2; }
die() { printf "${RED}[sync-vps]${NC} %s\n" "$*" >&2; exit 1; }

VPS_HOST="${VPS_HOST:-recon-vps}"
VPS_PATH="${VPS_PATH:-/opt/earn-money/}"

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    warn "working tree is dirty — only committed HEAD will be deployed"
fi

# --- Step 1: stage a clean tree from HEAD ---
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
log "staging git archive HEAD → $STAGE"
git archive HEAD | tar -x -C "$STAGE"

# --- Step 2: rsync staged tree to VPS ---
log "rsync → ${VPS_HOST}:${VPS_PATH}"
rsync -az --delete \
    --exclude='.env' \
    --exclude='.env.*' \
    --exclude='docker-compose.override.yml' \
    --exclude='flags/' \
    "$STAGE/" "${VPS_HOST}:${VPS_PATH}"

# --- Step 3: rebuild and restart all containers ---
log "docker compose up -d --build --force-recreate on ${VPS_HOST}"
ssh "${VPS_HOST}" "cd '${VPS_PATH}' && docker compose up -d --build --force-recreate" 2>&1

log "done — stack deployed on ${VPS_HOST}:${VPS_PATH}"
