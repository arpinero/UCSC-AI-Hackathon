#!/usr/bin/env bash
# Two-process smoke test against the REAL shared coordination database.
#
# Process A (tools-engineer) sends a REQUEST; process B (reasoning-engineer)
# receives it, replies; process A reads and acknowledges the reply.
#
# Run from any worktree of the forensics-agent repository:
#   bash scripts/smoke_two_process.sh [DB_PATH]
#
# NOTE: this proves the SQLite bus works across independent processes and
# worktrees. It does NOT prove that autonomous LLM coding sessions can receive
# messages without polling - see docs/CODING_AGENT_COMMUNICATION.md.
set -euo pipefail

DB="${1:-${FORENSICS_COORD_DB:-/home/asus/forensics-agent-coordination/coordination.db}}"
export FORENSICS_COORD_DB="$DB"
PY="${PYTHON:-python3}"
cd "$(dirname "$0")/.."   # run from the repo/worktree root so `coordination` imports

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

echo "== two-process smoke test against $DB =="

# --- Process A: tools-engineer sends a request ---------------------------
OUT_A=$("$PY" -m coordination.cli --json send \
  --sender tools-engineer --recipient reasoning-engineer \
  --type REQUEST --subject "smoke $STAMP: timeline contract question" \
  --body "Smoke test $STAMP: please confirm BuildTimelineArgs evidence_ids semantics.")
MSG_ID=$(echo "$OUT_A" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["message"]["message_id"])')
CORR_ID=$(echo "$OUT_A" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["message"]["correlation_id"])')
echo "A sent      message_id=$MSG_ID correlation_id=$CORR_ID"

# --- Process B: reasoning-engineer reads it and replies -------------------
OUT_B=$("$PY" -m coordination.cli --json inbox --agent reasoning-engineer)
COUNT=$(echo "$OUT_B" | "$PY" -c 'import json,sys; ms=json.load(sys.stdin); print(sum(1 for m in ms if m["message_id"]=="'"$MSG_ID"'"))')
[ "$COUNT" = "1" ] || { echo "FAIL: request not visible in reasoning-engineer inbox"; exit 1; }
"$PY" -m coordination.cli --json read --agent reasoning-engineer --message-id "$MSG_ID" >/dev/null
OUT_R=$("$PY" -m coordination.cli --json reply \
  --sender reasoning-engineer --to "$MSG_ID" \
  --body "Smoke reply $STAMP: evidence_ids must reference Evidence.evidence_id values.")
REPLY_ID=$(echo "$OUT_R" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["message"]["message_id"])')
echo "B replied   message_id=$REPLY_ID"

# --- Process A: reads and acknowledges the reply ---------------------------
OUT_C=$("$PY" -m coordination.cli --json read --agent tools-engineer --message-id "$REPLY_ID")
STATUS=$(echo "$OUT_C" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)[0]["status"])')
[ "$STATUS" = "READ" ] || { echo "FAIL: expected READ, got $STATUS"; exit 1; }
"$PY" -m coordination.cli --json ack --agent tools-engineer --message-id "$REPLY_ID" >/dev/null
OUT_D=$("$PY" -m coordination.cli --json history --correlation-id "$CORR_ID")
echo "$OUT_D" | "$PY" -c '
import json, sys
thread = json.load(sys.stdin)
assert len(thread) == 2, f"expected 2 messages in thread, got {len(thread)}"
assert thread[0]["message_type"] == "REQUEST" and thread[1]["message_type"] == "RESPONSE"
assert thread[1]["recipient"] == "tools-engineer"
assert thread[0]["status"] == "READ" and thread[1]["status"] == "ACKNOWLEDGED"
assert [m["seq"] for m in thread] == sorted(m["seq"] for m in thread)
print("thread verified: ordering, correlation, and status transitions OK")
'

# --- Cleanup: mark both smoke messages RESOLVED ----------------------------
"$PY" -m coordination.cli --json resolve --agent reasoning-engineer --message-id "$MSG_ID" >/dev/null
"$PY" -m coordination.cli --json resolve --agent tools-engineer --message-id "$REPLY_ID" >/dev/null
echo "PASS: two-process request/reply/ack exchange completed on $DB"

