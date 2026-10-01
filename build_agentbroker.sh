#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
bash scripts/build_hermes.sh
python build_trained_runtime.py
