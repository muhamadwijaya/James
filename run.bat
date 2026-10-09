@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo    pm3tool - Proxmark3 RFID Tool (GUI)
echo ============================================
echo.

REM --- cek Python ---
where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python tidak ditemukan.
  echo         Install dari https://www.python.org/downloads/
  echo         Saat install CENTANG "Add Python to PATH".
  echo.
  pause
  exit /b 1
)

REM --- pastikan PySide6 terpasang (sekali saja) ---
python -c "import PySide6" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Memasang PySide6 ... ^(sekali saja, perlu internet^)
  python -m pip install --upgrade pip
  python -m pip install PySide6
  if errorlevel 1 (
    echo [ERROR] Gagal memasang PySide6.
    pause
    exit /b 1
  )
)

REM --- jalankan GUI ---
echo [INFO] Menjalankan GUI ...
python -m pm3tool gui
if errorlevel 1 (
  echo.
  echo [ERROR] GUI gagal dijalankan. Periksa pesan di atas.
  pause
  exit /b 1
)

endlocal
