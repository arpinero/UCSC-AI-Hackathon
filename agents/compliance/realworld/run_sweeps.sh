#!/bin/bash
# Full model sweep on the GX10. The shared Ollama (0.23) can't pull newer tags, so a
# user-space Ollama runs on :11435 with a 16K context cap; models are tested one at a time.
cd "$(dirname "$0")"
NEW=~/ollama-new/bin/ollama
OLLAMA_HOST=127.0.0.1:11435 OLLAMA_CONTEXT_LENGTH=16384 OLLAMA_MAX_LOADED_MODELS=1 nohup $NEW serve > ollama-new.log 2>&1 &
sleep 8
(for m in gemma4:26b-a4b-it-qat gemma4:26b-nvfp4 gpt-oss:20b gemma4:12b-it-qat ministral-3:14b qwen3.6:35b-a3b-nvfp4 \
          granite4.2:30b nemotron-3-nano:30b gemma4:26b-a4b-it-mtp-q4_K_M qwen3.5:9b nemotron-3-nano:4b glm-4.7-flash lfm2.5:8b gemma4:26b; do
   echo "$(date +%T) pull $m" >> pull-new.log
   OLLAMA_HOST=127.0.0.1:11435 $NEW pull "$m" > /dev/null 2>> pull-new.log || echo "FAILED $m" >> pull-new.log
 done; echo "$(date +%T) pulls done" >> pull-new.log) &
SWEEP_IDLE_ROUNDS=0 python3 sweep.py > sweep.log 2>&1          # finish models on the shared server
OLLAMA_BASE=http://127.0.0.1:11435 python3 sweep.py > sweep-new.log 2>&1
