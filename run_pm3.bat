@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM --- UBAH baris ini bila ProxSpace Anda bukan di C:\ProxSpace ---
set "PROXSPACE=C:\ProxSpace"

echo ============================================
echo    pm3tool - Proxmark3 RFID Tool (GUI)
echo ============================================
echo ProxSpace: %PROXSPACE%
echo.

if not exist "%PROXSPACE%" goto :no_proxspace

REM --- cari proxmark3.exe ---
set "PM3_BINARY="
if exist "%PROXSPACE%\pm3\proxmark3\client\proxmark3.exe" set "PM3_BINARY=%PROXSPACE%\pm3\proxmark3\client\proxmark3.exe"
if not defined PM3_BINARY if exist "%PROXSPACE%\pm3\proxmark3\proxmark3.exe" set "PM3_BINARY=%PROXSPACE%\pm3\proxmark3\proxmark3.exe"
if defined PM3_BINARY goto :have_bin

echo Mencari proxmark3.exe (sebentar) ...
for /r "%PROXSPACE%" %%F in (proxmark3.exe) do if not defined PM3_BINARY set "PM3_BINARY=%%~fF"
if not defined PM3_BINARY goto :no_bin

:have_bin
set "PM3_PATH_ADD=%PROXSPACE%\msys2\mingw64\bin"
if not defined PM3_PORT set "PM3_PORT=com10"
echo Client : !PM3_BINARY!
echo DLL    : !PM3_PATH_ADD!
echo Port   : !PM3_PORT!
echo.

REM --- cari Python ---
set "PYEXE="
for %%P in ("py -3" "py" "python" "python3") do if not defined PYEXE (%%~P --version >nul 2>nul && set "PYEXE=%%~P")
if not defined PYEXE goto :no_python
echo Python : !PYEXE!
echo.

REM --- pastikan PySide6 ---
!PYEXE! -c "import PySide6" >nul 2>nul
if not errorlevel 1 goto :launch
echo Memasang PySide6 (sekali saja, perlu internet) ...
!PYEXE! -m pip install PySide6
if errorlevel 1 goto :no_qt

:launch
set "PATH=%PM3_PATH_ADD%;%PATH%"
echo Menjalankan GUI ... (tutup sesi 'pm3 --^>' interaktif dulu bila terbuka)
!PYEXE! -m pm3tool gui
echo.
echo GUI ditutup (kode keluar %errorlevel%).
goto :end

:no_proxspace
echo [ERROR] Folder ProxSpace tidak ada di "%PROXSPACE%".
echo         Buka file ini dengan Notepad dan ubah baris: set "PROXSPACE=..."
goto :end

:no_bin
echo [ERROR] proxmark3.exe tidak ditemukan di %PROXSPACE%.
echo         Pastikan sudah di-compile ('make') di ProxSpace.
goto :end

:no_python
echo [ERROR] Python tidak ada di PATH.
echo         Install dari https://www.python.org/downloads/ (centang "Add Python to PATH").
goto :end

:no_qt
echo [ERROR] Gagal memasang PySide6. Cek koneksi internet, lalu coba lagi.
goto :end

:end
echo.
pause
