#!/usr/bin/env bash
# Start the API. Creates the venv and installs deps on first run.
set -euo pipefail
cd "$(dirname "$0")/../backend"

if [ ! -d .venv ]; then
  echo "Creating virtualenv…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r requirements.txt
fi

echo "API on http://localhost:8000  (docs at /docs)"
exec ./.venv/bin/uvicorn app.main:app --reload --port 8000
