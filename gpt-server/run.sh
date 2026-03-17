#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if command -v docker >/dev/null 2>&1 && command -v docker compose >/dev/null 2>&1; then
  while true; do
    docker compose up --build
    sleep 2
  done
else
  python3 -m pip install -r api/requirements.txt
  while true; do
    uvicorn api.app:app --host 0.0.0.0 --port 8000 || true
    sleep 2
  done
fi
