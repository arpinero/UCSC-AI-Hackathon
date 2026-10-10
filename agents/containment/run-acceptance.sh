#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
mkdir -p logs results
# Wait for the full configured candidate; do not overlap GPU benchmark jobs.
until python3 -c 'import pathlib,json,sys; p=pathlib.Path("results/outcome-qwen-v3.json"); d=json.loads(p.read_text()) if p.exists() else {}; sys.exit(0 if d.get("mode")=="model" and d.get("planned")==48 and d.get("summary",{}).get("completed")==48 and d.get("config",{}).get("model")=="qwen3.6:35b" else 1)'; do sleep 15; done
systemctl --user stop containment-outcomes
python3 authorized_benchmark.py --resume > logs/authorized-qwen-v3.log 2>&1
python3 challenge_eval.py --resume --model qwen3.6:35b --endpoint http://127.0.0.1:11434/api --reasoning-effort none --max-tokens 6000 --output results/challenge-qwen-v3.json > logs/challenge-qwen-v3.log 2>&1
python3 evaluate.py --resume --model qwen3.6:35b --endpoint http://127.0.0.1:11434/api --reasoning-effort none --max-tokens 6000 --output results/smoke-qwen-v3.json > logs/smoke-qwen-v3.log 2>&1
