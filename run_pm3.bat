@echo off
REM ===========================================================
REM  Launcher pm3tool GUI untuk Windows + ProxSpace.
REM  Menjalankan GUI di Windows biasa, tapi otomatis mengarahkan
REM  ke proxmark3.exe milik ProxSpace + DLL-nya, jadi tombol
REM  Reader/Recover/Clone langsung bisa dipakai.
REM ===========================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- UBAH baris ini bila ProxSpace Anda bukan di C:\ProxSpace ---
set "PROXSPACE=C:\ProxSpace"

echo ============================================
echo    pm3tool - Proxmark3 RFID Tool (GUI)
echo ============================================
echo [INFO] ProxSpace: %PROXSPACE%

if not exist "%PROXSPACE%" (
  echo [ERROR] Folder ProxSpace tidak ada di "%PROXSPACE%".
  echo         Edit baris 'set "PROXSPACE=..."' di run_pm3.bat.
  pause
  exit /b 1
)

REM --- cari client proxmark3.exe ---
set "PM3_BINARY="
for %%D in (
  "%PROXSPACE%\pm3\proxmark3\client\proxmark3.exe"
  "%PROXSPACE%\pm3\proxmark3\proxmark3.exe"
) do (
  if not defined PM3_BINARY if exist "%%~D" set "PM3_BINARY=%%~D"
)
if not defined PM3_BINARY (
  echo [INFO] Mencari proxmark3.exe di %PROXSPACE% (sebentar) ...
  for /r "%PROXSPACE%" %%F in (proxmark3.exe) do (
    if not defined PM3_BINARY set "PM3_BINARY=%%~fF"
  )
)
if not defined PM3_BINARY (
  echo [ERROR] proxmark3.exe tidak ditemukan. Pastikan sudah 'make' di ProxSpace.
  pause
  exit /b 1
)

REM --- folder DLL MinGW + port default ---
set "PM3_PATH_ADD=%PROXSPACE%\msys2\mingw64\bin"
if not defined PM3_PORT set "PM3_PORT=com10"

echo [INFO] Client : !PM3_BINARY!
echo [INFO] DLL    : !PM3_PATH_ADD!
echo [INFO] Port   : !PM3_PORT!

REM --- cari Python ---
set "PYEXE="
for %%P in ("py -3" "py" "python" "python3") do (
  if not defined PYEXE ( %%~P --version >nul 2>nul && set "PYEXE=%%~P" )
)
if not defined PYEXE (
  echo [ERROR] Python tidak ada di PATH. Install dari python.org (centang Add to PATH).
  pause
  exit /b 1
)

REM --- pastikan PySide6 ---
!PYEXE! -c "import PySide6" >nul 2>nul
if errorlevel 1 (
  echo [INFO] Memasang PySide6 (sekali saja) ...
  !PYEXE! -m pip install PySide6 || ( echo [ERROR] gagal install PySide6 & pause & exit /b 1 )
)

REM --- tambahkan DLL ke PATH lalu jalankan GUI ---
set "PATH=%PM3_PATH_ADD%;%PATH%"
echo [INFO] Menjalankan GUI ... (tutup sesi 'pm3 -->' interaktif dulu bila terbuka)
!PYEXE! -m pm3tool gui
if errorlevel 1 ( echo. & echo [ERROR] GUI gagal. & pause )

endlocal
