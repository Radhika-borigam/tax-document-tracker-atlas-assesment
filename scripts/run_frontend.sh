#!/usr/bin/env bash
# Start the React dev server (proxies /api to the backend on :8000).
set -euo pipefail
cd "$(dirname "$0")/../frontend"

if [ ! -d node_modules ]; then
  echo "Installing frontend deps…"
  npm install
fi

echo "Frontend on http://localhost:5173"
exec npm run dev
