#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
mkdir -p logs results
# Wait for cold-start services before generating any scored responses.
ready=false
for attempt in $(seq 1 450); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null && curl -fsS http://127.0.0.1:11434/api/tags >/dev/null; then
    ready=true
    break
  fi
  sleep 2
done
$ready || exit 1
foundation() {
  python3 mitre_eval.py --resume --output results/mitre-foundation-policy.json > logs/mitre-foundation-policy-resume.log 2>&1
  python3 challenge_eval.py --resume --output results/challenge-foundation-policy.json > logs/challenge-foundation-policy.log 2>&1
  python3 evaluate.py --resume --output results/smoke-foundation-policy.json > logs/smoke-foundation-policy.log 2>&1
}
qwen() {
  python3 mitre_eval.py --resume --model qwen3.6:35b --endpoint http://127.0.0.1:11434/api --reasoning-effort none --max-tokens 6000 --output results/mitre-qwen-policy.json > logs/mitre-qwen-policy-resume.log 2>&1
  python3 challenge_eval.py --resume --model qwen3.6:35b --endpoint http://127.0.0.1:11434/api --reasoning-effort none --max-tokens 6000 --output results/challenge-qwen-policy.json > logs/challenge-qwen-policy.log 2>&1
  python3 evaluate.py --resume --model qwen3.6:35b --endpoint http://127.0.0.1:11434/api --reasoning-effort none --max-tokens 6000 --output results/smoke-qwen-policy.json > logs/smoke-qwen-policy.log 2>&1
}
foundation & foundation_pid=$!
qwen & qwen_pid=$!
failed=0
wait "$foundation_pid" || failed=1
wait "$qwen_pid" || failed=1
exit "$failed"
