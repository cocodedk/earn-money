#!/bin/sh
# Start a V3 agent mission and stream progress until completion.
#
# Usage:
#   ./scripts/run-mission.sh <target-host-or-uuid>
#   ./scripts/run-mission.sh juiceshop.cocode.dk
#   ./scripts/run-mission.sh 0be02808-dc57-4560-9688-bbd3fd1fca83
#
# Options (env):
#   API_BASE=http://localhost   — API base URL (nginx on port 80)
#   PROFILE=juice_shop_scoreboard
#   TIMEOUT=600                 — max seconds to wait for completion

set -eu

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { printf "${GREEN}[mission]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[mission]${NC} %s\n" "$*" >&2; }
die() { printf "${RED}[mission]${NC} %s\n" "$*" >&2; exit 1; }

TARGET_ARG="${1:-}"
[ -z "$TARGET_ARG" ] && die "Usage: $0 <target-host-or-uuid>"

API_BASE="${API_BASE:-http://localhost}"
PROFILE="${PROFILE:-juice_shop_scoreboard}"
TIMEOUT="${TIMEOUT:-600}"

# --- Resolve target (UUID or host lookup) ---
case "$TARGET_ARG" in
  *-*-*-*-*) TARGET_ID="$TARGET_ARG" ;;
  *)
    log "looking up target: $TARGET_ARG"
    TARGET_ID=$(curl -sf "$API_BASE/api/targets/?limit=200" \
      | python3 -c "
import os, sys, json
host = os.environ['TARGET_ARG']
d = json.load(sys.stdin)
for t in d['results']:
    if t['host'] == host:
        print(t['id']); break
else:
    print('')
")
    [ -z "$TARGET_ID" ] && die "No target with host '$TARGET_ARG'"
    ;;
esac
log "target ID: $TARGET_ID"

# --- Start mission ---
log "starting mission (profile=$PROFILE)"
SESSION=$(curl -sf -X POST "$API_BASE/api/agent/sessions/" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json, os
print(json.dumps({
    'target': os.environ['TARGET_ID'],
    'mission_profile': os.environ['PROFILE'],
}))
")")

SESSION_ID=$(echo "$SESSION" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
PHASES=$(echo "$SESSION" | python3 -c "import sys,json;print(' -> '.join(json.load(sys.stdin)['active_phases']))")
BUDGET=$(echo "$SESSION" | python3 -c "import sys,json;print(json.load(sys.stdin)['mission_budget']['max_turns'])")

log "session: $SESSION_ID"
log "phases: $PHASES"
log "budget: $BUDGET turns"
log "timeout: ${TIMEOUT}s"
echo ""

# --- Poll until terminal or timeout ---
PREV=""
FAIL_COUNT=0
START=$(date +%s)
while true; do
  ELAPSED=$(( $(date +%s) - START ))
  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    warn "timeout after ${TIMEOUT}s — session may still be running"
    break
  fi

  DATA=$(curl -sf "$API_BASE/api/agent/sessions/$SESSION_ID/" 2>/dev/null || echo "")
  if [ -z "$DATA" ]; then
    FAIL_COUNT=$((FAIL_COUNT + 1))
    if [ "$FAIL_COUNT" -ge 10 ]; then
      die "API unreachable after 10 consecutive failures"
    fi
    sleep 3
    continue
  fi
  FAIL_COUNT=0

  STATUS=$(echo "$DATA" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['status'])")
  PHASE=$(echo "$DATA" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['current_phase'])")
  TURNS=$(echo "$DATA" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('consumed_budget',{}).get('mission',{}).get('turns',0))")

  LINE="$STATUS | $PHASE | $TURNS/$BUDGET turns"
  if [ "$LINE" != "$PREV" ]; then
    printf "${CYAN}[%s]${NC} %s\n" "$(date +%H:%M:%S)" "$LINE"
    PREV="$LINE"
  fi

  case "$STATUS" in
    completed|stopped|failed) break ;;
  esac
  sleep 5
done

echo ""

# --- Show results ---
log "mission $STATUS after $TURNS turns"
log "fetching turn summary..."
echo ""

curl -sf "$API_BASE/api/agent/sessions/$SESSION_ID/turns/" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for t in d['results']:
    acts = t.get('actions', [])
    a = acts[0] if acts else {}
    goal = a.get('goal', '')[:65]
    atype = a.get('action_type', '?')
    phase = t['phase']
    vs = a.get('validation_status', '?')
    print(f'  Turn {t[\"index\"]:2d} | {phase:9s} | {atype:22s} | {vs:14s} | {goal}')
"

echo ""

curl -sf "$API_BASE/api/agent/sessions/$SESSION_ID/notes/" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
notes = d['results']
if notes:
    print('  Notes:')
    for n in notes:
        print(f'    {n[\"note_type\"]}: {json.dumps(n[\"content\"])[:80]}')
else:
    print('  No notes recorded.')
"
