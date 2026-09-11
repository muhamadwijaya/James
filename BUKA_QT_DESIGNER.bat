@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pyside6-designer.exe" goto missing
start "Qt Designer" ".venv\Scripts\pyside6-designer.exe" "ui\dashboard.ui"
exit /b 0
:missing
echo Jalankan JALANKAN_AGREGASI.bat satu kali untuk memasang PySide6 terlebih dahulu.
pause
exit /b 1
