#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
bash scripts/build_hermes.sh
python -m pip install -r requirements-memory.txt
python build_trained_runtime.py
