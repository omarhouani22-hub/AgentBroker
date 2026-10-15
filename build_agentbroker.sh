#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
time bash scripts/build_hermes.sh
time python -m pip install -r requirements-memory.txt
time python build_trained_runtime.py
