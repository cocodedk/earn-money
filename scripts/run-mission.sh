#!/bin/sh
# Start a V3 agent mission and stream progress until completion.
#
# Usage:
#   ./scripts/run-mission.sh <target-host>
#   ./scripts/run-mission.sh juiceshop.cocode.dk
#   ./scripts/run-mission.sh dvwa.cocode.dk
#
# Options (env):
#   API_BASE=http://localhost:8080   — API base URL
#   PROFILE=juice_shop_scoreboard   — mission profile name

set -eu

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log() { printf "${GREEN}[mission]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[mission]${NC} %s\n" "$*" >&2; }
die() { printf "${RED}[mission]${NC} %s\n" "$*" >&2; exit 1; }

TARGET_HOST="${1:-}"
[ -z "$TARGET_HOST" ] && die "Usage: $0 <target-host>"

API_BASE="${API_BASE:-http://localhost:8080}"
PROFILE="${PROFILE:-juice_shop_scoreboard}"

# --- Find target by host ---
log "looking up target: $TARGET_HOST"
TARGET_ID=$(curl -sf "$API_BASE/api/targets/" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for t in d['results']:
    if t['host'] == '$TARGET_HOST':
        print(t['id']); break
else:
    print('')
")

[ -z "$TARGET_ID" ] && die "No target found with host '$TARGET_HOST'"
log "target ID: $TARGET_ID"

# --- Start mission ---
log "starting mission (profile=$PROFILE)"
SESSION=$(curl -sf -X POST "$API_BASE/api/agent/sessions/" \
  -H "Content-Type: application/json" \
  -d "{\"target\": \"$TARGET_ID\", \"mission_profile\": \"$PROFILE\"}")

SESSION_ID=$(echo "$SESSION" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
PHASES=$(echo "$SESSION" | python3 -c "import sys,json;print(' → '.join(json.load(sys.stdin)['active_phases']))")
BUDGET=$(echo "$SESSION" | python3 -c "import sys,json;print(json.load(sys.stdin)['mission_budget']['max_turns'])")

log "session: $SESSION_ID"
log "phases: $PHASES"
log "budget: $BUDGET turns"
echo ""

# --- Poll until terminal ---
PREV=""
while true; do
  DATA=$(curl -sf "$API_BASE/api/agent/sessions/$SESSION_ID/" 2>/dev/null || echo "")
  [ -z "$DATA" ] && sleep 3 && continue

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
    print(f\"  Turn {t['index']:2d} | {phase:9s} | {atype:22s} | {goal}\")
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
        print(f\"    {n['note_type']}: {json.dumps(n['content'])[:80]}\")
else:
    print('  No notes recorded.')
"
