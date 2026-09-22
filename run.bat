@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PUBLISH_EXE=publish\Fukusuke.UniqueCode.Console.exe"
set "CONSOLE_PROJ=src\Fukusuke.UniqueCode.Console"

REM --- Muat konfigurasi API kalau ada ---
if exist "config.bat" call "config.bat"

REM --- Kalau API key masih kosong, tanyakan sekarang ---
if "%UniqueCodeApi__ApiKey%"=="" (
    echo.
    echo  [!] UniqueCodeApi__ApiKey belum diisi di config.bat
    echo.
    set /p UniqueCodeApi__ApiKey="     Masukkan x-api-key: "
    echo.
)

if "%UniqueCodeApi__BaseUrl%"=="" set "UniqueCodeApi__BaseUrl=https://devloyaltyapi.wingscorp.com"

REM --- Tanpa argumen: tampilkan bantuan ---
if "%~1"=="" goto :usage

echo ----------------------------------------------------------
echo  Base URL : %UniqueCodeApi__BaseUrl%
echo  Perintah : %*
echo ----------------------------------------------------------
echo.

REM --- Pakai EXE hasil publish kalau sudah ada, kalau belum pakai dotnet run ---
if exist "%PUBLISH_EXE%" (
    "%PUBLISH_EXE%" %*
) else (
    where dotnet >nul 2>&1
    if errorlevel 1 (
        echo  [X] Belum ada hasil build dan dotnet tidak ditemukan.
        echo      Jalankan build.bat terlebih dahulu.
        echo.
        pause
        exit /b 1
    )
    dotnet run --project "%CONSOLE_PROJ%" -c Release -- %*
)

echo.
pause
exit /b %errorlevel%


:usage
echo.
echo ==========================================================
echo   FUKUSUKE - Unique Code to Vendor Print
echo ==========================================================
echo.
echo   Cara pakai:
echo.
echo     run.bat request [eventId] [vendorId] [materialId] [quantity]
echo         Minta unique code untuk satu material/SKU.
echo         Contoh: run.bat request 13 6 000001 2
echo.
echo     run.bat confirm [eventId] [vendorId] [batchId] [code] [yyyy-MM-dd]
echo         Konfirmasi unique code yang sudah dicetak.
echo         Contoh: run.bat confirm 1 3 1 ABC123 2025-10-29
echo.
echo   Daftar materialId event 13 ^(contoh dari dokumentasi^):
echo     000001  Baby Happy Body Fit Pants BIG BAG S38+2
echo     000002  Baby Happy Body Fit Pants BIG BAG M32
echo     000003  Baby Happy Body Fit Pants BIG BAG L28
echo     ...     sampai 000015
echo.
pause
exit /b 0
