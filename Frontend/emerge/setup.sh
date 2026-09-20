#!/usr/bin/env bash
# FunRad - EMerge environment (Linux / WSL / macOS)
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3}
"$PY" -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
echo
echo "done. activate with:  source .venv/bin/activate"
echo "then:                 python coupler_catalogue.py"
echo "                      python redesign.py redesign_configs/final51_copper9.json"
