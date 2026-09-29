#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
test -d .venv || python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
PYTHONPATH=backend python main.py

