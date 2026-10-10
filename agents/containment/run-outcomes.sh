#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
mkdir -p logs results
# Avoid overlap with the prior regression suites; start after their service exits.
while systemctl --user is-active --quiet containment-evaluations; do sleep 10; done
curl -fsS http://127.0.0.1:8000/health >/dev/null
curl -fsS http://127.0.0.1:11434/api/tags >/dev/null
# Sequential model runs make benchmark load easier to interpret and preserve
# the larger serving slot for team use. Record actual inference latency per case.
python3 outcome_benchmark.py --resume --output results/outcome-foundation-v2.json > logs/outcome-foundation-v2.log 2>&1
python3 outcome_benchmark.py --resume --model qwen3.6:35b --endpoint http://127.0.0.1:11434/api --reasoning-effort none --max-tokens 6000 --output results/outcome-qwen-v2.json > logs/outcome-qwen-v2.log 2>&1
