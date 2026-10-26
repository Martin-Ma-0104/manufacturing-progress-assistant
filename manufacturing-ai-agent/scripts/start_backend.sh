#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x backend/.venv/bin/python ]]; then
  echo "First run: python3.12 -m venv backend/.venv && backend/.venv/bin/python -m pip install -r backend/requirements.txt"
  exit 1
fi
exec backend/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
