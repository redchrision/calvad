#!/bin/bash
set -e
cd "$(dirname "$0")"
[ -d .venv ] || { echo "Run ./setup.sh first"; exit 1; }
source .venv/bin/activate
trap 'kill 0' EXIT
(cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000) &
(cd frontend && npm run dev) &
sleep 2
if command -v open >/dev/null; then open http://127.0.0.1:5173; fi
echo "Calvad is running at http://127.0.0.1:5173"
wait
