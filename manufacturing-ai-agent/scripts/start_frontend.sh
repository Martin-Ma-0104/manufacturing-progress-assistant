#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../frontend"
if [[ ! -d node_modules ]]; then echo "First run: cd frontend && npm ci"; exit 1; fi
exec npm run dev
