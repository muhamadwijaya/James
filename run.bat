@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo    pm3tool - Proxmark3 RFID Tool (GUI)
echo ============================================
echo.

REM --- cari interpreter Python yang benar-benar jalan ---
REM Coba beberapa cara panggil; pakai yang pertama yang berhasil.
set "PYEXE="
for %%P in ("py -3" "py" "python" "python3") do (
  if not defined PYEXE (
    %%~P --version >nul 2>nul && set "PYEXE=%%~P"
  )
)

if not defined PYEXE (
  echo [ERROR] Python tidak bisa dipanggil dari Command Prompt.
  echo.
  echo   Python mungkin sudah terpasang, tapi tidak ada di PATH.
  echo   Coba salah satu:
  echo     1^) Buka Command Prompt, ketik:  py --version
  echo        Jika muncul versinya, PATH 'python' saja yang bermasalah.
  echo     2^) Install ulang dari https://www.python.org/downloads/
  echo        dan CENTANG "Add Python to PATH".
  echo     3^) Jika pakai Python dari Microsoft Store, matikan "App execution
  echo        aliases" untuk python di Settings, atau install dari python.org.
  echo.
  pause
  exit /b 1
)

echo [INFO] Memakai Python: !PYEXE!
!PYEXE! --version

REM --- pastikan PySide6 terpasang (sekali saja) ---
!PYEXE! -c "import PySide6" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Memasang PySide6 ... ^(sekali saja, perlu internet^)
  !PYEXE! -m pip install --upgrade pip
  !PYEXE! -m pip install PySide6
  if errorlevel 1 (
    echo [ERROR] Gagal memasang PySide6.
    pause
    exit /b 1
  )
)

REM --- jalankan GUI ---
echo [INFO] Menjalankan GUI ...
!PYEXE! -m pm3tool gui
if errorlevel 1 (
  echo.
  echo [ERROR] GUI gagal dijalankan. Periksa pesan di atas.
  pause
  exit /b 1
)

endlocal
