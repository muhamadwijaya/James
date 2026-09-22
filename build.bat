@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "SOLUTION=James.sln"
set "CONSOLE_PROJ=src\Fukusuke.UniqueCode.Console\Fukusuke.UniqueCode.Console.csproj"
set "PUBLISH_DIR=publish"
set "EXE_NAME=Fukusuke.UniqueCode.Console.exe"

echo.
echo ==========================================================
echo   FUKUSUKE - Unique Code to Vendor Print
echo   AUTO COMPILE (.NET 8)
echo ==========================================================
echo.

call :ensure_dotnet
if errorlevel 1 goto :fail_sdk

echo [1/4] Restore NuGet packages...
echo ----------------------------------------------------------
dotnet restore "%SOLUTION%"
if errorlevel 1 goto :fail_build
echo.

echo [2/4] Build Release...
echo ----------------------------------------------------------
dotnet build "%SOLUTION%" -c Release --no-restore
if errorlevel 1 goto :fail_build
echo.

echo [3/4] Run unit tests...
echo ----------------------------------------------------------
dotnet test "%SOLUTION%" -c Release --no-build
if errorlevel 1 goto :fail_test
echo.

echo [4/4] Publish single EXE...
echo ----------------------------------------------------------
dotnet publish "%CONSOLE_PROJ%" -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true -o "%PUBLISH_DIR%"
if errorlevel 1 goto :fail_build
echo.

echo ==========================================================
echo   BUILD SUCCESS
echo ==========================================================
echo.
echo   Program : %CD%\%PUBLISH_DIR%\%EXE_NAME%
echo.
echo   Langkah berikutnya:
echo     1. Buka config.bat, isi UniqueCodeApi__ApiKey dengan x-api-key Anda.
echo     2. Jalankan run.bat
echo.
echo   Contoh:
echo     run.bat request 13 6 000001 2
echo     run.bat confirm 1 3 1 ABC123 2025-10-29
echo.
pause
exit /b 0


REM ==========================================================
REM  Subroutine: pastikan .NET SDK tersedia
REM  global.json memakai rollForward latestMajor, jadi SDK 8
REM  atau yang lebih baru sama-sama bisa dipakai.
REM ==========================================================
:ensure_dotnet
where dotnet >nul 2>&1
if errorlevel 1 (
    echo  [!] .NET SDK belum terpasang di komputer ini.
    goto :offer_install
)

REM Baris hasil "dotnet --list-sdks" selalu diawali angka versi.
REM Kalau tidak ada, berarti yang terpasang cuma Runtime, bukan SDK.
dotnet --list-sdks 2>nul | findstr /r /c:"^[0-9]" >nul
if errorlevel 1 (
    echo  [!] Yang terpasang hanya .NET Runtime, SDK belum ada.
    goto :offer_install
)

echo  [OK] .NET SDK terdeteksi:
for /f "tokens=*" %%S in ('dotnet --list-sdks 2^>nul') do echo       %%S
echo.
exit /b 0

:offer_install
echo.
set "DOINSTALL="
set /p DOINSTALL="     Install .NET 8 SDK otomatis sekarang? (Y/N): "
if /i not "%DOINSTALL%"=="Y" exit /b 1

echo.
echo      Menginstall .NET 8 SDK...
echo ----------------------------------------------------------

where winget >nul 2>&1
if errorlevel 1 goto :install_via_script

winget install --id Microsoft.DotNet.SDK.8 -e --accept-source-agreements --accept-package-agreements
if not errorlevel 1 goto :recheck_dotnet
echo      winget gagal, mencoba installer resmi Microsoft...

:install_via_script
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://dot.net/v1/dotnet-install.ps1' -OutFile '%TEMP%\dotnet-install.ps1'"
if errorlevel 1 (
    echo      [X] Gagal mengunduh installer.
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\dotnet-install.ps1" -Channel 8.0 -InstallDir "%LOCALAPPDATA%\Microsoft\dotnet"
if errorlevel 1 (
    echo      [X] Instalasi gagal.
    exit /b 1
)
set "PATH=%LOCALAPPDATA%\Microsoft\dotnet;%PATH%"

:recheck_dotnet
echo.
where dotnet >nul 2>&1
if errorlevel 1 (
    echo      [X] dotnet masih belum terdeteksi.
    echo          Tutup jendela ini, buka CMD baru, jalankan build.bat lagi.
    exit /b 1
)
echo  [OK] .NET SDK siap.
echo.
exit /b 0


REM ==========================================================
REM  Error handlers
REM ==========================================================
:fail_sdk
echo.
echo ==========================================================
echo   GAGAL - .NET SDK tidak tersedia
echo ==========================================================
echo.
echo   Install manual dari:
echo     https://dotnet.microsoft.com/download/dotnet/8.0
echo.
echo   Lalu tutup CMD, buka baru, jalankan build.bat lagi.
echo.
pause
exit /b 1

:fail_build
echo.
echo ==========================================================
echo   GAGAL - Build error
echo ==========================================================
echo.
echo   Periksa pesan error di atas.
echo.
pause
exit /b 1

:fail_test
echo.
echo ==========================================================
echo   GAGAL - Ada unit test yang tidak lulus
echo ==========================================================
echo.
echo   Build berhasil, tapi ada test yang gagal. Lihat detail di atas.
echo.
pause
exit /b 1
