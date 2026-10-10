@echo off
REM Deteksi lokasi PM3 dan COM dilakukan otomatis oleh aplikasi.
REM Lokasi bawaan: C:\ProxSpace\pm3\proxmark3 (client atau client\build).
REM Pilihan manual opsional: PM3_BINARY, PM3_PORT, PM3_ROOT, PROXSPACE.
call "%~dp0run.bat"
exit /b %errorlevel%
