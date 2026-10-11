#!/usr/bin/env bash
set -euo pipefail
# NVIDIA ARM64 container; original BF16 weights, no quantization.
MODEL=fdtn-ai/Foundation-Sec-8B-Instruct
REVISION=aa13cb996e7fc700e7efd6b7367992f14cf349c0
IMAGE=nvcr.io/nvidia/vllm:26.01-py3
AGENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$AGENT_DIR/model-cache"
sudo docker run -d --name containment-model --restart unless-stopped \
  --device nvidia.com/gpu=all --ipc host \
  --ulimit memlock=-1 --ulimit stack=67108864 \
  -p 127.0.0.1:8000:8000 \
  -v "$AGENT_DIR/model-cache:/root/.cache/huggingface" \
  -e VLLM_ATTENTION_BACKEND=FLASHINFER \
  --entrypoint vllm "$IMAGE" serve "$MODEL" \
  --revision "$REVISION" --host 0.0.0.0 --port 8000 \
  --dtype bfloat16 --max-model-len 8192 --max-num-seqs 4 \
  --gpu-memory-utilization 0.3 --enforce-eager --enable-prefix-caching
