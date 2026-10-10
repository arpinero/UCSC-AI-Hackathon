#!/usr/bin/env bash
set -euo pipefail
AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$AGENT_DIR"
deadline=$((SECONDS + 14400))
echo 'Waiting for verified Q8 model download'
until test -f "$AGENT_DIR/models/foundation-sec-8b-instruct-q8_0.gguf"; do
  if [ "$SECONDS" -gt "$deadline" ]; then echo 'Download deadline reached'; exit 1; fi
  sleep 15
done
mkdir -p "$HOME/.config/systemd/user"
cp containment-model.service containment-api.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now containment-model containment-api
echo 'Model service started; waiting for inference health'
deadline=$((SECONDS + 900))
until curl -fsS http://127.0.0.1:8000/health >/dev/null; do
  if systemctl --user is-failed containment-model >/dev/null; then
    journalctl --user -u containment-model -n 80 --no-pager
    exit 1
  fi
  if [ "$SECONDS" -gt "$deadline" ]; then echo 'Inference startup deadline reached'; exit 1; fi
  sleep 10
done
echo 'Inference healthy'
python3 -m unittest -v test_agent
python3 evaluate.py --output results/evaluation.json
echo 'Setup and evaluation complete'
