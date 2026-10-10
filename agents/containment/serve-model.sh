#!/usr/bin/env bash
set -euo pipefail
AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /home/asus/llama.cpp/build/bin/llama-server \
  --model "$AGENT_DIR/models/foundation-sec-8b-instruct-q8_0.gguf" \
  --alias fdtn-ai/Foundation-Sec-8B-Instruct \
  --host 127.0.0.1 --port 8000 --n-gpu-layers 99 \
  --ctx-size 16384 --parallel 2 --flash-attn on --jinja
