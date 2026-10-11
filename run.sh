#!/usr/bin/env bash
# Proxmark3 RFID / NFC Toolkit - GUI launcher (Linux / macOS).
# Mirrors run.bat for non-Windows users.
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

if [ ! -x ".venv/bin/python" ]; then
    echo "[setup] Creating virtual environment ..."
    "$PY" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[setup] Installing dependencies ..."
python -m pip install --upgrade pip >/dev/null 2>&1 || true
python -m pip install -r requirements.txt

echo "[run] Starting Proxmark3 Toolkit GUI ..."
exec python main.py
