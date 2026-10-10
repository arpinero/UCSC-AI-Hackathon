#!/usr/bin/env bash
# Fixing agent model: Cisco Foundation-Sec-8B-Reasoning (Q8_0 GGUF) on llama.cpp.
# Port 8001 (containment uses 8000 and its API uses 8010).
set -euo pipefail
AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Weights are not stored in git; override FIXING_MODEL_DIR if they live elsewhere.
MODEL_DIR="${FIXING_MODEL_DIR:-/home/asus/fixing-agent/models}"
exec /home/asus/llama.cpp/build/bin/llama-server \
  --model "$MODEL_DIR/foundation-sec-8b-reasoning-q8_0.gguf" \
  --alias fdtn-ai/Foundation-Sec-8B-Reasoning \
  --chat-template-file "$AGENT_DIR/chat-template.jinja" \
  --host 127.0.0.1 --port 8001 --n-gpu-layers 99 \
  --ctx-size 32768 --parallel 2 --flash-attn on --jinja
