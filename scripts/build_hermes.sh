#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pip install -r requirements.txt
# Separate dependencies: Hermes currently pins a different cryptography version.
HERMES_REVISION=f80d888e2f6b3268c72c5ac32a55a63432751c0d
if [ ! -d .hermes-source/.git ]; then
  git init .hermes-source
  git -C .hermes-source remote add origin https://github.com/NousResearch/hermes-agent.git
fi
git -C .hermes-source fetch --depth 1 origin "$HERMES_REVISION"
git -C .hermes-source checkout --detach "$HERMES_REVISION"
python -m venv .hermes-runtime
# Upstream explicitly requires an editable installation; no patching of Hermes.
.hermes-runtime/bin/python -m pip install -e .hermes-source
HERMES_HOME="$(mktemp -d)" .hermes-runtime/bin/python -c 'from run_agent import AIAgent; print("Hermes import ready")'
