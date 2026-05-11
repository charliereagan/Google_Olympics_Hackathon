#!/usr/bin/env bash
# Bounded organic-op batch driver.
#
# Runs N stories sequentially: boot runtime → POST one prompt → wait for a
# new published_story to land → kill runtime → repeat. Each iteration is
# fully isolated; the autonomous loop has no chance to dispatch parallel
# investigations because the runtime is killed between stories.
#
# Cost-ceiling envs are pinned high (HOE-DEC-038 — no artificial cost
# barriers; the GCP $300 billing alert is the real wall).
#
# The Editor's autonomous-loop is also tuned long (~27 hours per cycle)
# so a single boot-cycle handles the full chain dispatch and never
# fires extra cycles before we kill the process.
#
# Usage:
#   scripts/run_bounded_batch.sh
#
# Edit PROMPTS array below to change the 5 stories.

set -euo pipefail

PROMPTS=(
  "Find the deepest Team USA winter-sport pipeline story rooted in Lake Placid, New York — its Olympic facility legacy, its institutional continuity, what makes the place keep producing winter Olympians and Paralympians."
  "Find a hometown story about Marquette, Michigan and Northern Michigan University's Nordic skiing program — the wax rooms, the school-day overlap with training, the multi-decade pipeline of cross-country skiers."
  "Find a Team USA story about Park City, Utah's alpine and freestyle skiing pipeline — the legacy 2002 Olympic facilities, how the public-school calendar bends around the chairlift schedule, the multi-generational tradition."
  "Find a hometown story about Hibbing, Minnesota's hockey pipeline — the indoor rink history, the iron-range school district, the pattern of small-town northern-Minnesota hockey towns producing Olympians."
  "Find a Team USA story about Bend, Oregon's endurance and adaptive sports pipeline — the high-altitude training, the Mt. Bachelor freestyle program, the local running and triathlon culture."
)

PROJECT="predictive-fx-495200-j4"
PORT=8080
WAIT_SEC=900   # 15 min max per story

cd "$(dirname "$0")/.."

# Activate venv
# shellcheck disable=SC1091
source .venv/bin/activate

baseline_count() {
  python -c "
from google.cloud import firestore
db = firestore.Client(project='${PROJECT}')
print(sum(1 for _ in db.collection('published_stories').limit(100).stream()))
" 2>/dev/null
}

current_count() {
  python -c "
from google.cloud import firestore
db = firestore.Client(project='${PROJECT}')
print(sum(1 for _ in db.collection('published_stories').limit(100).stream()))
" 2>/dev/null
}

for i in "${!PROMPTS[@]}"; do
  N=$((i+1))
  PROMPT="${PROMPTS[$i]}"
  echo ""
  echo "=================================================================="
  echo "Story ${N} / ${#PROMPTS[@]}"
  echo "Prompt: ${PROMPT:0:120}..."
  echo "=================================================================="

  # Kill any leftover runtime
  pkill -f "uvicorn agents.runtime" 2>/dev/null || true
  sleep 2

  BEFORE=$(baseline_count)
  echo "  baseline published_stories: ${BEFORE}"

  # Boot runtime. Cost ceilings are pinned absurdly high (HOE-DEC-038 — no
  # artificial barriers). Editor think-cycle keeps the default 30-90s
  # because the chain needs multiple cycles to advance Scout → Investigator
  # → Storyteller → Publish Gate → Narrator. Dispatch sprawl is bounded by
  # prompts/editor.md's "one new investigation at a time" rule, NOT by
  # cycle frequency.
  GOOGLE_CLOUD_PROJECT=${PROJECT} \
  COST_CEILING_DAILY_USD=10000 \
  COST_CEILING_ABSOLUTE_USD=10000 \
  COST_CEILING_GEMINI_PRO_TOKENS=999999999 \
  COST_CEILING_GROUNDING_QUERIES=999999999 \
  COST_CEILING_DEEP_RESEARCH_CALLS=999999999 \
  COST_CEILING_TTS_CHARS=999999999 \
  nohup uvicorn agents.runtime:app --port ${PORT} --log-level warning > /tmp/agent-runtime-batch-${N}.log 2>&1 &
  RUNTIME_PID=$!
  echo "  runtime pid=${RUNTIME_PID}"

  # Wait for ready
  for j in 1 2 3 4 5 6 7 8 9 10; do
    CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${PORT}/health/heartbeat || echo "000")
    if [ "$CODE" = "200" ]; then break; fi
    sleep 3
  done

  # POST the prompt
  RESP=$(curl -sX POST http://localhost:${PORT}/api/investigate \
    -H "Content-Type: application/json" \
    -d "{\"prompt\": $(python -c "import json,sys; print(json.dumps(sys.argv[1]))" "$PROMPT"), \"compression_factor\": 1.0, \"source\": \"bounded_batch_${N}\"}")
  echo "  POST response: ${RESP}"

  # Wait until published_stories increases
  echo "  waiting for new published_story (max ${WAIT_SEC}s)..."
  ELAPSED=0
  while [ $ELAPSED -lt $WAIT_SEC ]; do
    sleep 60
    ELAPSED=$((ELAPSED + 60))
    AFTER=$(current_count)
    if [ "$AFTER" -gt "$BEFORE" ]; then
      echo "  ✓ new published_story landed after ${ELAPSED}s (count: ${BEFORE} → ${AFTER})"
      break
    fi
    echo "    [${ELAPSED}s] still ${AFTER} published_stories..."
  done

  AFTER=$(current_count)
  if [ "$AFTER" -le "$BEFORE" ]; then
    echo "  ✗ TIMEOUT — no new published_story after ${WAIT_SEC}s (count still ${AFTER})"
    echo "  killing runtime; logs at /tmp/agent-runtime-batch-${N}.log"
  fi

  # Kill runtime cleanly
  kill -9 $RUNTIME_PID 2>/dev/null || true
  pkill -f "uvicorn agents.runtime" 2>/dev/null || true
  sleep 2
done

echo ""
echo "=================================================================="
echo "Bounded batch complete."
echo "Final published_stories count: $(current_count)"
echo "=================================================================="
