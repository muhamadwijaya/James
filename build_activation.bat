@echo off
rem ==========================================================================
rem  Build aplikasi PEMBUAT LISENSI (vendor) menjadi 1 file .exe
rem    Hasil: dist\FRTCam-Aktivasi.exe
rem  Aplikasi ini HANYA untuk vendor (pembuat kode aktivasi), jangan dibagikan
rem  ke pelanggan. Kunci privat vendor disimpan di folder "vendor_keys" di
rem  sebelah .exe saat Anda klik "Buat kunci vendor sendiri".
rem ==========================================================================
setlocal EnableExtensions
cd /d "%~dp0"
title Build FRT Cam - Pembuat Lisensi

set "APP_NAME=FRTCam-Aktivasi"
set "ROOT=%~dp0"
set "BUILD=%ROOT%build"
set "DIST=%ROOT%dist"
set "VENV=%ROOT%.venv"
set "VPY=%VENV%\Scripts\python.exe"

echo ============================================================
echo   Build %APP_NAME%  [GUI PySide6 - khusus vendor]
echo ============================================================
echo.

echo [1/2] Menyiapkan Python...
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto :python_found
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto :python_found
echo [GAGAL] Python 3.9 atau lebih baru tidak ditemukan.
echo         Install dari https://www.python.org/downloads/ (centang Add to PATH).
goto :fail

:python_found
echo       Python : %PY%
if exist "%VPY%" goto :venv_ready
echo       Membuat virtual environment .venv ...
%PY% -m venv "%VENV%"
if errorlevel 1 goto :fail

:venv_ready
echo       Install dependency: PySide6 dan PyInstaller ...
"%VPY%" -m pip install --disable-pip-version-check -q --upgrade pip >nul 2>&1
"%VPY%" -m pip install --disable-pip-version-check -q -r "%ROOT%requirements.txt"
if errorlevel 1 goto :fail

echo.
echo [2/2] Build GUI pembuat lisensi menjadi .exe ...
"%VPY%" -m PyInstaller --noconfirm --clean --onefile --windowed --log-level WARN ^
  --name "%APP_NAME%" ^
  --distpath "%DIST%" ^
  --workpath "%BUILD%\pyinstaller-vendor" ^
  --specpath "%BUILD%" ^
  --paths "%ROOT%gui" ^
  --icon "%ROOT%assets\app.ico" ^
  "%ROOT%gui\vendor_app.py"
if errorlevel 1 goto :fail
if not exist "%DIST%\%APP_NAME%.exe" goto :fail

echo.
echo ============================================================
echo   SELESAI
echo.
echo   Aplikasi vendor : %DIST%\%APP_NAME%.exe
echo.
echo   Simpan .exe ini untuk Anda sendiri (jangan dibagikan ke pelanggan).
echo   Klik "Buat kunci vendor sendiri" sekali, tempel kunci publik ke
echo   gui\activation.py, lalu build ulang aplikasi utama dengan build.bat.
echo ============================================================
if not defined NO_PAUSE pause
exit /b 0

:fail
echo.
echo ============================================================
echo   BUILD GAGAL - lihat pesan error di atas.
echo ============================================================
if not defined NO_PAUSE pause
exit /b 1
