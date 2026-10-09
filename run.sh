#!/usr/bin/env bash
# Launcher pm3tool (Linux/macOS). Windows pakai run.bat.
set -e
cd "$(dirname "$0")"

echo "============================================"
echo "   pm3tool - Proxmark3 RFID Tool (GUI)"
echo "============================================"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "[ERROR] python3 tidak ditemukan. Install Python 3.10+."
  exit 1
fi

if ! "$PY" -c "import PySide6" >/dev/null 2>&1; then
  echo "[INFO] Memasang PySide6 (sekali saja)..."
  "$PY" -m pip install PySide6
fi

echo "[INFO] Menjalankan GUI..."
exec "$PY" -m pm3tool gui
