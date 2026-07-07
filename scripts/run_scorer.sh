#!/usr/bin/env bash
# Restart the GraphJudge scorer for the demo — personal-domain reference graph,
# detached on 0.0.0.0:8888 so it survives the launching shell/session ending.
#
# Usage (from anywhere):   bash /workspace/HackWithBay/HackWithBay_repo/scripts/run_scorer.sh
# In Claude Code prompt:   ! bash scripts/run_scorer.sh
#
# Reads all config (Neo4j creds, OPENROUTER_API_KEY, CONSUME_CREDIT_URL,
# EXTRACT_PROMPT_PATH=personal) from .env. Logs to scorer.log.
set -u
REPO=/workspace/HackWithBay/HackWithBay_repo
cd "$REPO" || { echo "repo not found: $REPO"; exit 1; }

# free the port (kills any old scorer), then launch fully detached
fuser -k 8888/tcp 2>/dev/null || true
pkill -f '\.venv/bin/python -c .*uvicorn.run\("scorer.app:app".*port=8888' 2>/dev/null || true
sleep 1
setsid bash -c 'SCORER_REFERENCE_BACKEND=auto PIPELINE_USE_ROCKETRIDE=${PIPELINE_USE_ROCKETRIDE:-1} ROCKETRIDE_URI=${ROCKETRIDE_URI:-ws://localhost:5565} ROCKETRIDE_APIKEY=${ROCKETRIDE_APIKEY:-graphjudge-local-rocketride} PYTHONPATH='"$REPO"' nohup .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(\"'"$REPO"'/.env\"); import uvicorn; uvicorn.run(\"scorer.app:app\", host=\"0.0.0.0\", port=8888)" >> '"$REPO"'/scorer.log 2>&1' < /dev/null &
disown 2>/dev/null || true

# wait for health
for _ in $(seq 1 25); do
  if curl -s --max-time 2 http://127.0.0.1:8888/health >/dev/null 2>&1; then
    echo "scorer UP:"
    curl -s http://127.0.0.1:8888/health
    echo
    exit 0
  fi
  sleep 1
done
echo "scorer FAILED to come up within 25s — check $REPO/scorer.log"
exit 1
