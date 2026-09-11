@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto deps
where py >nul 2>nul
if errorlevel 1 goto usepython
py -3 runtime_check.py
if errorlevel 1 goto failed
py -3 -m venv .venv
if errorlevel 1 goto failed
goto deps
:usepython
python runtime_check.py
if errorlevel 1 goto failed
python -m venv .venv
if errorlevel 1 goto failed
:deps
.venv\Scripts\python.exe runtime_check.py
if errorlevel 1 goto failed
.venv\Scripts\python.exe runtime_check.py --dependencies >nul 2>nul
if not errorlevel 1 goto run
echo Memasang dependensi yang sesuai dengan versi Python...
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe runtime_check.py --dependencies
if errorlevel 1 goto failed
:run
.venv\Scripts\python.exe main.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Aplikasi belum dapat dijalankan. Periksa pesan error di atas.
echo Didukung: Python standar 3.10-3.14 64-bit.
echo Instalasi dependensi pertama membutuhkan internet.
echo Baca PERBAIKAN_PYTHON_314.md untuk petunjuk pembaruan.
pause
exit /b 1
