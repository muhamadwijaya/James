#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -f .venv/bin/python ]; then
  python3 runtime_check.py
  python3 -m venv .venv
fi
.venv/bin/python runtime_check.py
if ! .venv/bin/python runtime_check.py --dependencies >/dev/null 2>&1; then
  .venv/bin/python -m pip install --only-binary=:all: -r requirements.txt
  .venv/bin/python runtime_check.py --dependencies
fi
exec .venv/bin/python main.py "$@"
