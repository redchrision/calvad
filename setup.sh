#!/bin/bash
set -e
cd "$(dirname "$0")"
command -v python3 >/dev/null || { echo "Python 3 is required."; exit 1; }
command -v npm >/dev/null || { echo "Node/npm is required. Install Node.js first."; exit 1; }
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cd frontend && npm install
printf '\nCalvad setup complete.\nNext: make sure Ollama is installed and run: ollama pull qwen2.5:7b\nThen run ./start.sh\n'