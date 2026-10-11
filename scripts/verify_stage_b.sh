#!/usr/bin/env bash
# Full Stage B verification for the integration-qa workstream.
#
# Runs: pytest (full suite) + ruff + mypy + the two-process coordination
# bus smoke test, then prints a clear PASS/FAIL summary.
#
# Usage: bash scripts/verify_stage_b.sh [DB_PATH]
set -u
cd "$(dirname "$0")/.."

VENV_BIN="${FORENSICS_VENV:-/home/asus/forensics-agent/.venv/bin}"
DB="${1:-${FORENSICS_COORD_DB:-/home/asus/forensics-agent-coordination/coordination.db}}"
export FORENSICS_COORD_DB="$DB"

PYTEST="$VENV_BIN/pytest"
RUFF="$VENV_BIN/ruff"
MYPY="$VENV_BIN/mypy"

NAMES=("pytest" "ruff" "mypy" "bus-smoke")
RESULTS=()

echo "== Stage B verification (integration-qa) =="

echo "--- pytest (full suite) ---"
if "$PYTEST" > /tmp/stageb_pytest.log 2>&1; then
  RESULTS+=("PASS"); tail -5 /tmp/stageb_pytest.log
else
  RESULTS+=("FAIL"); tail -40 /tmp/stageb_pytest.log
fi

echo "--- ruff check . ---"
if "$RUFF" check . > /tmp/stageb_ruff.log 2>&1; then
  RESULTS+=("PASS"); tail -2 /tmp/stageb_ruff.log
else
  RESULTS+=("FAIL"); tail -40 /tmp/stageb_ruff.log
fi

echo "--- mypy (contracts, coordination, forensics) ---"
if "$MYPY" > /tmp/stageb_mypy.log 2>&1; then
  RESULTS+=("PASS"); tail -2 /tmp/stageb_mypy.log
else
  RESULTS+=("FAIL"); tail -40 /tmp/stageb_mypy.log
fi

echo "--- two-process coordination bus smoke test ---"
if bash scripts/smoke_two_process.sh "$DB" > /tmp/stageb_smoke.log 2>&1; then
  RESULTS+=("PASS"); tail -3 /tmp/stageb_smoke.log
else
  RESULTS+=("FAIL"); tail -20 /tmp/stageb_smoke.log
fi

echo
echo "================ SUMMARY ================"
FAILED=0
for i in "${!NAMES[@]}"; do
  printf '%-12s %s\n' "${NAMES[$i]}" "${RESULTS[$i]}"
  [ "${RESULTS[$i]}" = "PASS" ] || FAILED=$((FAILED + 1))
done
echo "=========================================="
if [ "$FAILED" -eq 0 ]; then
  echo "RESULT: PASS — all checks green"
  exit 0
else
  echo "RESULT: FAIL — $FAILED check(s) failed (logs: /tmp/stageb_*.log)"
  exit 1
fi
