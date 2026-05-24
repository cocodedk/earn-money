#!/bin/sh
# Push git-tracked files to the VPS and rebuild containers.
# Idempotent. Destructive — rsync --delete wipes anything on the
# VPS path that isn't in the source tree.
#
# Defaults (override via env):
#   VPS_HOST=recon-vps           — SSH host alias from ~/.ssh/config
#   VPS_PATH=/opt/earn-money/    — install prefix on the VPS
#
# Only git-tracked files are synced (via git ls-files). Untracked
# files, .gitignore'd paths, and local state never reach the VPS.

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

# Warn on any dirty state (tracked modifications + untracked files)
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    warn "working tree is dirty (modifications or untracked files)"
    warn "only git-tracked files will be synced"
fi

# --- Step 1: rsync git-tracked files only ---
log "rsync (git-tracked) → ${VPS_HOST}:${VPS_PATH}"
git ls-files -z | rsync -az --delete \
    --files-from=- --from0 \
    ./ "${VPS_HOST}:${VPS_PATH}"

# --- Step 2: rebuild and restart all containers ---
log "docker compose up -d --build --force-recreate on ${VPS_HOST}"
ssh "${VPS_HOST}" "cd '${VPS_PATH}' && docker compose up -d --build --force-recreate" 2>&1

log "done — stack deployed on ${VPS_HOST}:${VPS_PATH}"
